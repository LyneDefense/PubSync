from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.synthesis import Critic, SynthesisBudget, SynthesisTrace, SensorResult, TaskGuide, humanize_event, run_synthesis
from app.blogger_distillation import analysis, artifacts
from app.blogger_distillation.modality import (
    ALL as SCOPE_ALL,
    IMAGE_TEXT,
    TALKING_VIDEO,
    VISUAL_VIDEO,
    subtype_label,
)
from app.blogger_distillation.service.crud import archive_active_skills
from app.blogger_distillation.service.events import (
    DistillationCancelled,
    ensure_distillation_not_cancelled,
    record_task_event,
)
from app.blogger_distillation.tikhub_client import TikHubUsage
from app.config import Settings
from app.models import (
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
)
from app.services.ai_service import AIServiceError, create_json_response

logger = logging.getLogger(__name__)


@dataclass
class DistillationResult:
    run: BloggerDistillationRun
    skill: BloggerSkill


def build_distillation_diagnostics(posts: list[BloggerPost], stats: dict[str, Any]) -> dict[str, int]:
    stats_json = json.dumps(stats, ensure_ascii=False, default=str)
    return {
        "sample_count": len(posts),
        "video_count": sum(1 for post in posts if post.content_type == "video"),
        "transcript_count": sum(1 for post in posts if (post.transcript_text or "").strip()),
        "transcript_chars": sum(len(post.transcript_text or "") for post in posts),
        "comment_total": int(stats.get("comment_total") or 0),
        "stats_json_chars": len(stats_json),
        "stats_prompt_chars": min(len(stats_json), 18000),
    }


def normalize_mode(mode: str | None) -> str:
    """A=拆解对标博主（默认）；B=诊断我的账号。其它一律按 A 处理。"""
    return "B" if str(mode or "").strip().upper() == "B" else "A"


def run_blogger_distillation(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    collection_run_id: int,
    mode: str = "A",
    subtypes: list[str] | None = None,
) -> DistillationResult:
    mode = normalize_mode(mode)
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    collection_run = db.get(BloggerCollectionRun, collection_run_id)
    if not collection_run or collection_run.tenant_id != tenant_id or collection_run.blogger_id != blogger.id:
        raise ValueError("采集批次不存在或不属于当前博主")
    if collection_run.status != "succeeded":
        raise ValueError("只能基于已完成的采集批次进行蒸馏")

    run = BloggerDistillationRun(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        collection_run_id=collection_run.id,
        task_id=task_id,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(db, tenant_id, task_id, "采集批次", "succeeded", f"使用采集批次 #{collection_run.id}，样本={collection_run.post_count}")
        post_ids = list(
            db.scalars(
                select(BloggerCollectionPost.post_id)
                .where(BloggerCollectionPost.collection_run_id == collection_run.id)
                .order_by(BloggerCollectionPost.position.asc(), BloggerCollectionPost.id.asc())
            )
        )
        posts = list(
            db.scalars(
                select(BloggerPost)
                .where(
                    BloggerPost.id.in_(post_ids),
                    BloggerPost.tenant_id == tenant_id,
                    BloggerPost.blogger_id == blogger.id,
                    BloggerPost.status != "delisted",
                )
                .order_by(BloggerPost.score.desc(), BloggerPost.created_at.desc())
            )
        )
        if not posts:
            raise ValueError("采集批次没有可用于蒸馏的样本")
        # 按所选内容模态过滤 + 最低样本门槛;空=全选=通用 skill。
        valid_subtypes = (IMAGE_TEXT, TALKING_VIDEO, VISUAL_VIDEO)
        selected = [s for s in (subtypes or []) if s in valid_subtypes]
        if selected:
            counts = Counter(post.content_subtype for post in posts)
            too_few = [s for s in selected if counts.get(s, 0) < settings.distill_min_samples_per_subtype]
            if too_few:
                labels = "、".join(subtype_label(s) for s in too_few)
                raise ValueError(f"以下模态样本不足 {settings.distill_min_samples_per_subtype} 条，无法蒸馏：{labels}")
            posts = [post for post in posts if post.content_subtype in selected]
            if not posts:
                raise ValueError("所选模态在该采集批次没有样本")
            scope = selected
            record_task_event(
                db, tenant_id, task_id, "蒸馏范围", "succeeded",
                f"按所选模态蒸馏：{('、'.join(subtype_label(s) for s in selected))}，样本 {len(posts)} 条",
            )
        else:
            scope = [SCOPE_ALL]
        record_task_event(db, tenant_id, task_id, "认知蒸馏", "running", "开始用大模型提炼认知、策略和执行层方法论")
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        stats = analysis.analyze_posts(posts)
        try:
            collection_summary = json.loads(collection_run.summary_json or "{}")
            if isinstance(collection_summary, dict) and collection_summary.get("quality_report"):
                stats["quality_report"] = collection_summary["quality_report"]
        except json.JSONDecodeError:
            pass
        user_info: dict[str, Any] = {"homepage_url": blogger.homepage_url, "nickname": blogger.display_name}
        diagnostics = build_distillation_diagnostics(posts, stats)
        logger.info(
            "认知蒸馏诊断：任务ID=%s，平台=%s，博主ID=%s，批次ID=%s，样本=%s，视频=%s，转写样本=%s，总转写字数=%s，评论=%s，stats字符=%s，发送字符=%s，模型=%s",
            task_id,
            blogger.platform,
            blogger.id,
            collection_run.id,
            diagnostics["sample_count"],
            diagnostics["video_count"],
            diagnostics["transcript_count"],
            diagnostics["transcript_chars"],
            diagnostics["comment_total"],
            diagnostics["stats_json_chars"],
            diagnostics["stats_prompt_chars"],
            settings.minimax_text_model if settings.minimax_api_key else settings.openai_text_model,
        )
        llm_started_at = time.perf_counter()
        logger.info("认知蒸馏请求已发送：任务ID=%s，平台=%s，模型=%s", task_id, blogger.platform, settings.minimax_text_model if settings.minimax_api_key else settings.openai_text_model)

        def on_distill_event(kind: str, event: dict[str, Any]) -> None:
            triple = humanize_event(kind, event, subject="博主方法论", gerund="提炼")
            if triple:
                step, status, message = triple
                record_task_event(db, tenant_id, task_id, step, status, message)

        distillation, synthesis_trace = distill_with_llm(settings, blogger, user_info, stats, mode, on_event=on_distill_event)
        quality = evaluate_distillation_quality(distillation, stats, mode)
        quality["revisions"] = synthesis_trace.revisions
        quality["final_passed"] = synthesis_trace.final_passed
        llm_elapsed = time.perf_counter() - llm_started_at
        logger.info(
            "认知蒸馏返回：任务ID=%s，平台=%s，耗时=%.2fs，输出字段=%s，输出字符=%s",
            task_id,
            blogger.platform,
            llm_elapsed,
            len(distillation),
            len(json.dumps(distillation, ensure_ascii=False, default=str)),
        )
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        usage = TikHubUsage()
        report_html = artifacts.render_report_html(blogger, stats, distillation, usage, mode=mode, quality=quality)
        skill_markdown = artifacts.build_skill_markdown(blogger, stats, distillation, mode=mode, scope=scope)
        skill_desc = (
            f"基于你自己的小红书账号 {blogger.display_name} 蒸馏出的创作基因与增长诊断"
            if mode == "B"
            else f"基于小红书博主 {blogger.display_name} 公开内容蒸馏出的创作方法论"
        )
        skill = BloggerSkill(
            tenant_id=tenant_id,
            blogger_id=blogger.id,
            run_id=run.id,
            name=artifacts.slug_skill_name(blogger.display_name, mode),
            description=skill_desc,
            skill_markdown=skill_markdown,
            scope_json=json.dumps(scope, ensure_ascii=False),
            status="pending_confirmation",
        )
        db.add(skill)

        run.status = "pending_confirmation"
        run.sample_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        run.tikhub_request_count = collection_run.tikhub_request_count
        run.tikhub_estimated_cost_usd = collection_run.tikhub_estimated_cost_usd
        run.tikhub_cost_min_usd = collection_run.tikhub_cost_min_usd
        run.tikhub_cost_max_usd = collection_run.tikhub_cost_max_usd
        run.report_json = json.dumps(
            {"mode": mode, "stats": stats, "distillation": distillation, "quality": quality, "synthesis": synthesis_trace.to_dict()},
            ensure_ascii=False,
            default=str,
        )
        run.report_html = report_html
        db.commit()
        db.refresh(run)
        db.refresh(skill)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "Skill 生成",
            "succeeded",
            f"蒸馏完成，等待确认：批次 #{collection_run.id}，质量评分 {quality['score']}（{quality['grade']}），自我修订 {synthesis_trace.revisions} 次",
            {
                "collection_run_id": collection_run.id,
                "run_id": run.id,
                "skill_id": skill.id,
                "mode": mode,
                "quality_score": quality["score"],
                "quality_grade": quality["grade"],
                "revisions": synthesis_trace.revisions,
            },
        )
        return DistillationResult(run=run, skill=skill)
    except DistillationCancelled as exc:
        run.status = "cancelled"
        run.error_message = str(exc)
        db.commit()
        raise
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise


def confirm_blogger_distillation(db: Session, tenant_id: int, run_id: int) -> DistillationResult:
    run = db.get(BloggerDistillationRun, run_id)
    if not run or run.tenant_id != tenant_id:
        raise ValueError("蒸馏结果不存在或不属于当前工作空间")
    if run.status != "pending_confirmation":
        raise ValueError("只能保存待确认的蒸馏结果")
    blogger = db.get(BloggerProfile, run.blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("蒸馏结果对应的博主不存在")
    skill = db.scalar(
        select(BloggerSkill).where(
            BloggerSkill.tenant_id == tenant_id,
            BloggerSkill.blogger_id == blogger.id,
            BloggerSkill.run_id == run.id,
            BloggerSkill.status == "pending_confirmation",
        )
    )
    if not skill:
        raise ValueError("待确认 Skill 不存在")

    archive_active_skills(db, tenant_id, blogger.id)
    skill.status = "active"
    run.status = "succeeded"
    blogger.last_distilled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    db.refresh(skill)
    logger.info("博主蒸馏结果已保存：租户=%s，运行ID=%s，Skill ID=%s", tenant_id, run.id, skill.id)
    return DistillationResult(run=run, skill=skill)


def abandon_blogger_distillation(db: Session, tenant_id: int, run_id: int) -> BloggerDistillationRun:
    run = db.get(BloggerDistillationRun, run_id)
    if not run or run.tenant_id != tenant_id:
        raise ValueError("蒸馏结果不存在或不属于当前工作空间")
    if run.status != "pending_confirmation":
        raise ValueError("只能放弃待确认的蒸馏结果")
    skill = db.scalar(
        select(BloggerSkill).where(
            BloggerSkill.tenant_id == tenant_id,
            BloggerSkill.run_id == run.id,
            BloggerSkill.status == "pending_confirmation",
        )
    )
    if skill:
        skill.status = "abandoned"
    run.status = "abandoned"
    db.commit()
    db.refresh(run)
    logger.info("博主蒸馏结果已放弃：租户=%s，运行ID=%s", tenant_id, run.id)
    return run


@dataclass
class DistillContext:
    """一次蒸馏合成的上下文，贯穿 guide/sensors/critic。"""

    blogger: BloggerProfile
    user_info: dict[str, Any]
    stats: dict[str, Any]
    mode: str


def build_distill_prompt(ctx: DistillContext) -> str:
    """构造三层蒸馏的基础提示词（feedforward guide）。"""
    blogger = ctx.blogger
    user_info = ctx.user_info
    stats = ctx.stats
    if ctx.mode == "B":
        mode_framing = (
            "模式 B：诊断我的账号。下面这个账号就是用户本人的账号，目标不是模仿别人，"
            "而是照镜子——指出账号已经做对的地方、明显的短板，以及可立即执行的增长动作。"
            "self_diagnosis 字段必填且要具体、可执行。"
        )
    else:
        mode_framing = (
            "模式 A：拆解对标博主。把对标博主的公开内容提炼成用户可以借鉴、迁移到自己账号的"
            "创作方法论。self_diagnosis 返回空对象（用户本人不是这个账号）。"
        )

    return f"""
你是“博主蒸馏器”的分析引擎，复刻 blogger-distiller 的方法论：脚本已经做完确定性统计，你负责把
公开内容蒸馏成「认知层 / 策略层 / 内容层」三层、可迁移、可执行的创作方法论。

{mode_framing}

硬边界：
- 不能冒充原博主，不能复制原文、原标题、原图或个人经历。
- 只提炼公开内容里的选题逻辑、结构、表达策略、评论需求和创作边界。
- 输出必须是合法 JSON 对象，不要 Markdown、不要 HTML、不要解释过程、不要 <think>。
- 每一条结论都要尽量贴着“代码统计与代表样本”里的事实和数字，不要泛泛而谈、不要正确的废话。
- 列表里每一项是一句可执行的话；空缺就给空数组，不要编造。

重要口径（防止把视频当长图文）：
- body_text / body_excerpt 只代表图文笔记的文字描述，不能混入视频字幕或 ASR 转写。
- transcript_text / transcript_excerpt 是视频字幕/口播转写，属于“视频口播素材”，不是图文正文。
- 如果样本以视频为主，content_layer.body_structures 可以为空，必须改在 video_script_structures 里
  分析“口播切入方式、信息密度、结尾方式”，不要写成“正文平均几千字”。

博主：
{json.dumps({"display_name": blogger.display_name, "homepage_url": blogger.homepage_url, "niche": blogger.niche, "description": blogger.description, "platform": blogger.platform}, ensure_ascii=False)}

TikHub 用户信息摘要：
{json.dumps(user_info, ensure_ascii=False, default=str)[:3000]}

代码统计与代表样本（含 hot_posts 爆款样本，可用其 title/external_id/score 做来源标注）：
{json.dumps(stats, ensure_ascii=False, default=str)[:17000]}

只输出下面这个 JSON（字段必须齐全；不确定的列表给空数组）：
{{
  "one_glance": "一句话说清这个账号的价值和爆款原因（带关键数字）",
  "persona": {{"identity": "身份感/人设", "stance": "表达姿态", "trust_source": "信任来源"}},
  "audience": "目标读者画像",
  "cognitive_layer": {{
    "core_beliefs": ["核心信念：TA 默认相信什么"],
    "opinion_tensions": ["观点张力/反共识：TA 常对抗的常识"],
    "value_stance": ["价值立场"],
    "thinking_models": ["反复出现的思维模式"]
  }},
  "strategy_layer": {{
    "series_planning": ["系列/选题规划方式"],
    "trend_hijacking": ["蹭热点/借势方式"],
    "ops_habits": ["运营习惯：发布、互动、引导"],
    "posting_rhythm": "发布节奏一句话总结（结合 frequency_info）"
  }},
  "content_layer": {{
    "title_formulas": ["标题公式 TOP5，结合 title_patterns 的占比"],
    "opening_templates": ["开头模板 TOP3，结合 opening_patterns"],
    "body_structures": ["图文正文结构，只能基于 body_text/body_excerpt；视频为主则可空"],
    "video_script_structures": ["视频口播/字幕结构，只能基于 transcript；无转写则空数组"],
    "emotional_rhythm": ["情绪节奏/留人钩子公式"],
    "language_dna": ["语言 DNA：高频表达、句式节奏、人称策略、口头禅。若样本同时含图文与口播(见 subtype_counts)，每条须以「书面：」或「口播：」开头分别标注，书面只依据 body_text、口播只依据 transcript，绝不混为一谈"],
    "cta_strategy": ["CTA/互动引导策略，结合 cta_patterns"],
    "cover_text_rules": ["封面文案规律"],
    "hashtag_strategy": ["标签策略，结合 frequent_hashtags"]
  }},
  "top_post_breakdowns": [
    {{"rank": 1, "title_ref": "爆款样本标题(可截断)", "source": "样本来源：external_id 或标题", "why_viral": "为什么火（贴数据）", "reusable_tactic": "可复用的具体技巧"}}
  ],
  "comment_insights": ["评论区暴露的读者真实需求和互动机会"],
  "growth_trend": "结合 growth_trend/数据面板的发展趋势与机会，一段话",
  "sample_topics": ["可迁移到用户自己账号的新选题示例 TOP8"],
  "contrast_examples": [{{"plain": "普通写法", "better": "更贴近该方法论的写法"}}],
  "do_not_do": ["创作禁区/不该模仿的部分"],
  "self_diagnosis": {{"strengths": ["模式B：账号优势"], "weaknesses": ["模式B：明显短板"], "action_plan": ["模式B：可立即执行的增长动作"]}},
  "core_conclusion": "给用户的核心使用建议（一段话）"
}}
"""
class DistillSchemaSensor:
    """计算型阻断传感器：三层结构必须有最低限度内容，否则强制修订。"""

    name = "结构完整性"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        cognitive = result.get("cognitive_layer", {}) or {}
        content = result.get("content_layer", {}) or {}
        missing: list[str] = []
        if not any(cognitive.get(key) for key in ("core_beliefs", "opinion_tensions", "value_stance", "thinking_models")):
            missing.append("认知层(cognitive_layer)四个子项全空，至少补全核心信念与观点张力")
        if not (content.get("title_formulas") or content.get("body_structures") or content.get("video_script_structures")):
            missing.append("内容层缺少标题公式与正文/口播结构，至少补全标题公式与一种结构")
        if missing:
            return SensorResult(passed=False, issues=missing, corrective_feedback="；".join(missing))
        return SensorResult(passed=True)


class DistillQualitySensor:
    """计算型评分传感器：复用确定性质量评估，给分并附改进项。"""

    name = "质量评分"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        quality = evaluate_distillation_quality(result, ctx.stats, ctx.mode)
        feedback = "；".join(quality["issues"]) if quality["issues"] else ""
        return SensorResult(passed=True, score=quality["score"], issues=quality["issues"], corrective_feedback=feedback)


def make_distill_critic(settings: Settings, model: str | None) -> Critic:
    """推理型评审（inferential sensor）：让模型对蒸馏结果挑刺，产出面向模型的纠错指令。"""

    def critic(result: dict[str, Any], ctx: DistillContext) -> str:
        prompt = f"""你是博主蒸馏结果的资深审稿人。下面是一份蒸馏 JSON 和原始统计。
请挑出最多 5 条最该改进的问题（空泛无据、与统计/样本矛盾、把视频当图文、爆款拆解缺来源标注、
认知层不够锋利等），每条给出具体怎么改。

只输出 JSON：{{"feedback": "一段中文纠错指令，分条列出问题与改法"}}

原始统计：{json.dumps(ctx.stats, ensure_ascii=False, default=str)[:6000]}
蒸馏结果：{json.dumps(result, ensure_ascii=False, default=str)[:6000]}
"""
        data = create_json_response(settings, prompt, model=model)
        feedback = data.get("feedback")
        return str(feedback).strip() if isinstance(feedback, str) else ""

    return critic


def distill_with_llm(
    settings: Settings,
    blogger: BloggerProfile,
    user_info: dict[str, Any],
    stats: dict[str, Any],
    mode: str = "A",
    on_event: Any = None,
) -> tuple[dict[str, Any], SynthesisTrace]:
    """复刻 blogger-distiller 的「三层蒸馏」，并用合成循环（生成→校验→修订）包裹：
    生成 → 计算型传感器校验（结构+质量分）→ 不达标则叠加推理型评审反馈修订，直到达标或用尽预算。
    返回（蒸馏结果, 合成轨迹）。"""
    mode = normalize_mode(mode)
    ctx = DistillContext(blogger=blogger, user_info=user_info, stats=stats, mode=mode)
    model = (settings.distill_text_model or "").strip() or None
    guide = TaskGuide(
        name="博主蒸馏",
        build_prompt=build_distill_prompt,
        normalize=lambda data, c: normalize_distillation(data, c.mode),
    )
    sensors = [DistillSchemaSensor(), DistillQualitySensor()]
    critic = make_distill_critic(settings, model) if settings.synthesis_llm_critic_enabled else None
    budget = SynthesisBudget(
        max_attempts=1 + max(0, settings.synthesis_max_revise_iterations),
        min_score=settings.synthesis_min_quality_score,
    )
    result, trace = run_synthesis(settings, guide, ctx, sensors, budget, model=model, critic=critic, on_event=on_event)
    if is_distillation_empty(result):
        raise AIServiceError("博主蒸馏经多轮修订后认知层与内容层仍为空，判定为无效输出")
    return result, trace


# 蒸馏输出的三层结构骨架，缺字段时用它补齐，保证下游渲染与质量评估稳定。
LAYER_KEYS: dict[str, list[str]] = {
    "cognitive_layer": ["core_beliefs", "opinion_tensions", "value_stance", "thinking_models"],
    "strategy_layer": ["series_planning", "trend_hijacking", "ops_habits", "posting_rhythm"],
    "content_layer": [
        "title_formulas",
        "opening_templates",
        "body_structures",
        "video_script_structures",
        "emotional_rhythm",
        "language_dna",
        "cta_strategy",
        "cover_text_rules",
        "hashtag_strategy",
    ],
}


def normalize_distillation(data: dict[str, Any], mode: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise AIServiceError("博主蒸馏结果不是 JSON 对象")
    # 三层结构缺失时给出兜底骨架，避免渲染/质量评估崩溃。
    for layer, keys in LAYER_KEYS.items():
        layer_value = data.get(layer)
        if not isinstance(layer_value, dict):
            layer_value = {}
        for key in keys:
            if key == "posting_rhythm":
                layer_value.setdefault(key, "")
            else:
                value = layer_value.get(key)
                layer_value[key] = value if isinstance(value, list) else ([] if value in (None, "") else [value])
        data[layer] = layer_value
    persona = data.get("persona")
    if not isinstance(persona, dict):
        data["persona"] = {"identity": str(persona or ""), "stance": "", "trust_source": ""}
    data.setdefault("one_glance", "")
    data.setdefault("audience", "")
    for list_key in ("top_post_breakdowns", "comment_insights", "sample_topics", "contrast_examples", "do_not_do"):
        value = data.get(list_key)
        data[list_key] = value if isinstance(value, list) else ([] if value in (None, "") else [value])
    data.setdefault("growth_trend", "")
    data.setdefault("core_conclusion", "")
    diagnosis = data.get("self_diagnosis")
    if not isinstance(diagnosis, dict):
        diagnosis = {}
    for key in ("strengths", "weaknesses", "action_plan"):
        value = diagnosis.get(key)
        diagnosis[key] = value if isinstance(value, list) else ([] if value in (None, "") else [value])
    data["self_diagnosis"] = diagnosis
    # 注意：这里不再因「三层为空」抛错——空/坏结构由 DistillSchemaSensor 判定为不通过，
    # 交给合成修订循环重试；多轮后仍为空才在 distill_with_llm 末尾硬失败。
    return data


def is_distillation_empty(data: dict[str, Any]) -> bool:
    """三层核心是否整体为空（结构性无效）。"""
    cognitive = data.get("cognitive_layer", {}) or {}
    content = data.get("content_layer", {}) or {}
    cognitive_empty = not any(cognitive.get(k) for k in ("core_beliefs", "opinion_tensions", "value_stance", "thinking_models"))
    content_empty = not any(content.get(k) for k in ("title_formulas", "opening_templates", "body_structures", "video_script_structures"))
    return cognitive_empty and content_empty


def evaluate_distillation_quality(distillation: dict[str, Any], stats: dict[str, Any], mode: str) -> dict[str, Any]:
    """P0 质量自检：用确定性规则给蒸馏结果打分，并列出可改进项。不阻断保存，但显著前置展示。"""
    issues: list[str] = []
    checks: list[dict[str, Any]] = []
    score = 100

    def deduct(amount: int, name: str, ok: bool, detail: str) -> None:
        nonlocal score
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            score -= amount
            issues.append(detail)

    cognitive = distillation.get("cognitive_layer", {})
    strategy = distillation.get("strategy_layer", {})
    content = distillation.get("content_layer", {})

    cognitive_items = sum(len(cognitive.get(k) or []) for k in ("core_beliefs", "opinion_tensions", "value_stance", "thinking_models"))
    deduct(20, "认知层覆盖", cognitive_items >= 4, f"认知层共有 {cognitive_items} 条，建议 ≥4 条（核心信念/观点张力/价值立场/思维模式）")

    strategy_items = sum(len(strategy.get(k) or []) for k in ("series_planning", "trend_hijacking", "ops_habits"))
    deduct(10, "策略层覆盖", strategy_items >= 2, f"策略层共有 {strategy_items} 条，建议 ≥2 条")

    title_count = len(content.get("title_formulas") or [])
    deduct(15, "标题公式", title_count >= 3, f"标题公式 {title_count} 条，建议 ≥3 条")

    has_body = bool(content.get("body_structures"))
    has_video = bool(content.get("video_script_structures"))
    deduct(10, "正文/口播结构", has_body or has_video, "图文正文结构与视频口播结构均为空")

    # 视频/图文一致性：视频为主却没分析口播结构 = 严重问题
    transcript_info = stats.get("transcript_info") or {}
    sample_count = max(int(stats.get("sample_count") or 0), 1)
    video_count = int(transcript_info.get("video_count") or 0)
    transcript_count = int(transcript_info.get("transcript_count") or 0)
    video_heavy = video_count / sample_count >= 0.5
    video_ok = (not video_heavy) or (transcript_count == 0) or has_video
    deduct(15, "视频口播一致性", video_ok, "样本以视频为主且有字幕，但没有产出视频口播结构（可能把视频当图文分析）")

    # 爆款逐条拆解 + 来源标注（grounding）
    breakdowns = distillation.get("top_post_breakdowns") or []
    hot_available = len(stats.get("hot_posts") or [])
    expected = min(3, hot_available) if hot_available else 0
    deduct(15, "TOP爆款拆解", len(breakdowns) >= expected, f"爆款逐条拆解 {len(breakdowns)} 条，建议 ≥{expected} 条")
    sourced = sum(1 for item in breakdowns if isinstance(item, dict) and str(item.get("source") or "").strip())
    deduct(5, "来源标注", expected == 0 or sourced >= 1, "爆款拆解缺少来源标注（source），可追溯性不足")

    # 空泛检测：内容层条目过短视为空话
    content_items = [str(x) for k in ("title_formulas", "opening_templates", "language_dna", "cta_strategy") for x in (content.get(k) or [])]
    short_items = sum(1 for x in content_items if len(x.strip()) < 8)
    vague_ok = not content_items or short_items / max(len(content_items), 1) < 0.4
    deduct(5, "空泛检测", vague_ok, f"内容层有 {short_items}/{len(content_items)} 条过短，疑似空泛")

    if mode == "B":
        diag = distillation.get("self_diagnosis", {})
        diag_items = sum(len(diag.get(k) or []) for k in ("strengths", "weaknesses", "action_plan"))
        deduct(10, "自我诊断(模式B)", diag_items >= 3, f"诊断模式但 self_diagnosis 仅 {diag_items} 条，建议补全优势/短板/行动")

    score = max(0, min(100, score))
    grade = "优" if score >= 85 else ("良" if score >= 70 else "待改进")
    return {"score": score, "grade": grade, "issues": issues, "checks": checks, "mode": mode}
