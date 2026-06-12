from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation import analysis, artifacts
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


def run_blogger_distillation(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    collection_run_id: int,
) -> DistillationResult:
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
                .where(BloggerPost.id.in_(post_ids), BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger.id)
                .order_by(BloggerPost.score.desc(), BloggerPost.created_at.desc())
            )
        )
        if not posts:
            raise ValueError("采集批次没有可用于蒸馏的样本")
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
        distillation = distill_with_llm(settings, blogger, user_info, stats)
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
        report_html = artifacts.render_report_html(blogger, stats, distillation, usage)
        skill_markdown = artifacts.build_skill_markdown(blogger, stats, distillation)
        skill = BloggerSkill(
            tenant_id=tenant_id,
            blogger_id=blogger.id,
            run_id=run.id,
            name=artifacts.slug_skill_name(blogger.display_name),
            description=f"基于小红书博主 {blogger.display_name} 公开内容蒸馏出的创作方法论",
            skill_markdown=skill_markdown,
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
        run.report_json = json.dumps({"stats": stats, "distillation": distillation}, ensure_ascii=False, default=str)
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
            f"蒸馏完成，等待确认：批次 #{collection_run.id}",
            {"collection_run_id": collection_run.id, "run_id": run.id, "skill_id": skill.id},
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


def distill_with_llm(settings: Settings, blogger: BloggerProfile, user_info: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
你是“博主蒸馏 skill”的分析器。请参考 blogger-distiller 的方法：脚本负责事实统计，你负责把公开内容提炼成可迁移的创作方法论。

边界：
- 不能冒充原博主。
- 不能复制原文、标题、图片或个人经历。
- 只能提炼公开内容中的选题、结构、表达策略、评论需求和创作边界。
- 输出必须是合法 JSON，不要 Markdown，不要 HTML，不要解释过程。
- 你必须优先基于“代码统计与代表样本”，不要泛泛而谈。

博主：
{json.dumps({"display_name": blogger.display_name, "homepage_url": blogger.homepage_url, "niche": blogger.niche, "description": blogger.description}, ensure_ascii=False)}

TikHub 用户信息摘要：
{json.dumps(user_info, ensure_ascii=False, default=str)[:4000]}

代码统计与代表样本：
{json.dumps(stats, ensure_ascii=False, default=str)[:18000]}

重要口径：
- body_text / body_excerpt 只代表小红书笔记原始文字描述，不能混入视频字幕或 ASR 转写。
- transcript_text / transcript_excerpt 代表视频字幕或视频口播转写，属于“视频口播素材”，不是图文长文正文。
- structure_info 只描述图文正文结构；transcript_info 只描述视频口播/字幕结构。
- 如果样本以视频为主，必须分析“视频口播结构、切入方式、结尾方式、信息密度”，不要写成“长文模式”或“正文平均几千字”。
- 可以说“视频口播/字幕平均长度约 X 字”，但不能把这个数字当成图文正文长度。

输出 JSON：
{{
  "one_glance": "一句话说清这个账号的内容价值和爆款原因",
  "positioning": "这个博主公开内容呈现出的账号定位",
  "persona": ["人设拆解：身份感、表达姿态、信任来源"],
  "audience": "目标读者画像",
  "cognitive_model": ["认知层方法论"],
  "topic_strategy": ["选题策略"],
  "title_patterns": ["标题规律"],
  "opening_patterns": ["开头规律"],
  "body_structures": ["图文正文/笔记描述结构，只能基于 body_text/body_excerpt"],
  "video_script_structures": ["视频口播/字幕结构，只能基于 transcript_text/transcript_excerpt；如果没有视频转写则返回空数组"],
  "content_formula": ["可复用的内容公式"],
  "language_dna": ["语言风格、情绪节奏、常用表达方式"],
  "cover_text_rules": ["封面文案规律"],
  "hashtag_strategy": ["标签策略"],
  "comment_strategy": ["评论区洞察和互动策略"],
  "growth_insights": ["基于数据面板的发展趋势和机会"],
  "sample_topics": ["可迁移的新选题示例"],
  "contrast_examples": ["对比示例：普通写法 -> 更贴近该方法论的写法"],
  "do_not_do": ["禁止事项和不应模仿的部分"],
  "core_conclusion": "最后给用户的核心使用建议"
}}
"""
    data = create_json_response(settings, prompt)
    required = ["positioning", "audience", "cognitive_model", "topic_strategy", "title_patterns", "body_structures", "do_not_do"]
    for key in required:
        if key not in data:
            raise AIServiceError(f"博主蒸馏结果缺少字段：{key}")
    data.setdefault("one_glance", data.get("positioning", ""))
    data.setdefault("persona", [])
    data.setdefault("content_formula", data.get("body_structures", []))
    data.setdefault("video_script_structures", [])
    data.setdefault("language_dna", [])
    data.setdefault("growth_insights", [])
    data.setdefault("contrast_examples", [])
    data.setdefault("core_conclusion", data.get("positioning", ""))
    return data
