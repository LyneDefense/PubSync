import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation.service.events import record_task_event
from app.blogger_dossier.audience import parse_audience
from app.compliance import scan_creation
from app.config import Settings
from app.models import AppSetting, BloggerDistillationRun, BloggerPost, BloggerProfile, BloggerSkill, XhsPublishPackage
from app.xhs_creation.my_baseline import summarize_video_baseline
from app.schemas import XhsPublishPackageCreate, XhsPublishPackageSave, XhsTopicIdeaRequest
from app.prompts import anti_injection, output_schema, render_schema, rules_block
from app.services.ai_service import AIServiceError, create_json_response, is_ai_enabled
from app.xhs_creation.schema import TopicIdeas
from app.synthesis import humanize_event, run_agent
from app.xhs_creation.agent import (
    CreationContext,
    build_benchmark_comparison,
    build_creation_agent,
    evaluate_creation_quality,
)
from app.xhs_creation.normalize import (
    build_fallback_image_plan,
    normalize_image_plan,
    normalize_script,
    normalize_string_list,
    resolve_image_count,
    social_platform_name,
)

logger = logging.getLogger(__name__)

# 本轮 AI 创作只支持小红书/抖音;公众号留架构槽,暂不放行。
SUPPORTED_CREATION_PLATFORMS = {"xhs", "douyin"}


def generate_xhs_publish_package_draft(
    db: Session,
    settings: Settings,
    tenant_id: int,
    payload: XhsPublishPackageCreate,
    task_id: str | None = None,
) -> dict[str, Any]:
    skill, blogger = validate_xhs_package_request(db, settings, tenant_id, payload)
    platform_name = social_platform_name(blogger.platform)

    logger.info(
        "%s发布包草稿生成开始：租户=%s，博主=%s，skill_id=%s，类型=%s，主题=%s",
        platform_name,
        tenant_id,
        blogger.display_name,
        skill.id,
        payload.content_type,
        payload.topic,
    )
    generated, trace, benchmark, quality, compliance = generate_package_content(
        db, settings, tenant_id, blogger, skill, payload, task_id=task_id
    )
    image_plan = normalize_image_plan(generated.get("image_plan"))
    image_urls: list[str] = []  # 不再替用户自动生图,保留空列表兼容下游/存量。
    error_message: str | None = None

    if payload.content_type == "image_note":
        # 只出「配图方案」(张数 + 每张:用途/图上文案/版式/中文生图 prompt),不代生成图片
        # —— 省图像模型成本,用户拿 prompt 去自己的 AI 工具生成。
        target_count = resolve_image_count(payload.image_count_mode, payload.requested_image_count, generated, image_plan)
        image_plan = image_plan[:target_count]
        if target_count and not image_plan:
            image_plan = build_fallback_image_plan(generated, target_count)
        if task_id and image_plan:
            record_task_event(db, tenant_id, task_id, "配图方案", "succeeded", f"已给出 {len(image_plan)} 张配图方案(含生图 prompt)")

    draft = {
        "tenant_id": tenant_id,
        "blogger_id": blogger.id,
        "skill_id": skill.id,
        "content_type": payload.content_type,
        "topic": payload.topic,
        "target_audience": payload.target_audience,
        "content_goal": payload.content_goal,
        "keywords": payload.keywords,
        "image_count_mode": payload.image_count_mode,
        "requested_image_count": payload.requested_image_count,
        "title": str(generated.get("title") or "").strip(),
        "body_text": str(generated.get("body_text") or "").strip(),
        "hashtags_json": json.dumps(normalize_string_list(generated.get("hashtags")), ensure_ascii=False),
        "cover_text": str(generated.get("cover_text") or "").strip(),
        "image_plan_json": json.dumps(image_plan, ensure_ascii=False),
        "image_urls_json": json.dumps(image_urls, ensure_ascii=False),
        "script_json": json.dumps(normalize_script(generated.get("script"), payload.content_type), ensure_ascii=False),
        "status": "draft",
        "error_message": error_message,
        # 过程与评判(随草稿透传,不入库):合成轨迹、对标对比、质量评分、合规结果。
        "synthesis": trace.to_dict(),
        "benchmark": benchmark,
        "quality": quality,
        "compliance": compliance,
    }
    logger.info(
        "%s发布包草稿生成完成：skill_id=%s，配图方案=%s 张，自我修订=%s，质量=%s",
        platform_name,
        skill.id,
        len(image_plan),
        trace.revisions,
        quality.get("score"),
    )
    return draft


def create_xhs_publish_package(
    db: Session,
    tenant_id: int,
    payload: XhsPublishPackageSave,
) -> XhsPublishPackage:
    skill = db.get(BloggerSkill, payload.skill_id)
    if not skill or skill.tenant_id != tenant_id or skill.status != "active":
        raise ValueError("Skill 不存在或不可用")
    blogger = db.get(BloggerProfile, skill.blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("Skill 对应的博主不存在")

    # 目标「我的账号」可选;给了就校验归属 + 是 mine 类型(没绑账号的用户传 None 即可)。
    my_account_id = getattr(payload, "my_account_id", None)
    if my_account_id is not None:
        my_account = db.get(BloggerProfile, my_account_id)
        if not my_account or my_account.tenant_id != tenant_id or my_account.account_type != "mine":
            raise ValueError("目标账号不存在或不是「我的账号」")

    package = XhsPublishPackage(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        skill_id=skill.id,
        my_account_id=my_account_id,
        content_type=payload.content_type,
        topic=payload.topic,
        target_audience=payload.target_audience,
        content_goal=payload.content_goal,
        keywords=payload.keywords,
        image_count_mode=payload.image_count_mode,
        requested_image_count=payload.requested_image_count,
        title=payload.title.strip(),
        body_text=payload.body_text,
        hashtags_json=payload.hashtags_json,
        cover_text=payload.cover_text.strip(),
        image_plan_json=payload.image_plan_json,
        image_urls_json=payload.image_urls_json,
        script_json=payload.script_json,
        status="generated",
        error_message=payload.error_message,
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    logger.info("%s发布包保存完成：package_id=%s，skill_id=%s", social_platform_name(blogger.platform), package.id, skill.id)
    return package


def validate_xhs_package_request(
    db: Session,
    settings: Settings,
    tenant_id: int,
    payload: XhsPublishPackageCreate,
) -> tuple[BloggerSkill, BloggerProfile]:
    skill = db.get(BloggerSkill, payload.skill_id)
    if not skill or skill.tenant_id != tenant_id or skill.status != "active":
        raise ValueError("Skill 不存在或不可用")
    blogger = db.get(BloggerProfile, skill.blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("Skill 对应的博主不存在")
    if blogger.platform not in SUPPORTED_CREATION_PLATFORMS:
        raise ValueError("当前平台暂不支持 AI 创作")
    if payload.content_type == "image_note" and payload.image_count_mode == "manual" and not payload.requested_image_count:
        raise ValueError("手动配图数量至少为 1")
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    return skill, blogger


def generate_xhs_topic_ideas(
    db: Session,
    settings: Settings,
    tenant_id: int,
    payload: XhsTopicIdeaRequest,
) -> list[dict[str, Any]]:
    skill = db.get(BloggerSkill, payload.skill_id)
    if not skill or skill.tenant_id != tenant_id or skill.status != "active":
        raise ValueError("Skill 不存在或不可用")
    blogger = db.get(BloggerProfile, skill.blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("Skill 对应的博主不存在")
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    platform_name = social_platform_name(blogger.platform)
    audience = _my_account_audience(db, tenant_id, payload.my_blogger_id)

    logger.info(
        "%s选题方案生成开始：租户=%s，对标博主=%s，skill_id=%s，我的账号=%s，受众数据=%s，种子主题=%s",
        platform_name,
        tenant_id,
        blogger.display_name,
        skill.id,
        payload.my_blogger_id,
        "有" if audience else "无",
        payload.seed_topic,
    )
    intent_block = json.dumps(
        {
            "seed_topic": payload.seed_topic,
            "target_audience": payload.target_audience,
            "content_goal": payload.content_goal,
            "keywords": payload.keywords,
        },
        ensure_ascii=False,
        indent=2,
    )
    rules = rules_block(
        "只学 <benchmark> 里的选题方法、标题结构、切入角度;不要冒充原博主、不要复制原文、不要照搬其题材。",
        "每个选题都要落在 <my_audience> 给出的**我的账号读者真实关心的问题**上,让选题是“我的读者真的想看”,而不是对标博主的读者想看。",
        "若 <intent> 里填了意图(种子主题/目标人群/内容目的/关键词),把选题收敛到该意图;意图与受众需求冲突时以意图为准。",
        "每个方案让用户一眼看出:写什么、怎么切、适合谁、为什么值得写。",
        anti_injection("<benchmark>", "<my_audience>", "<intent>"),
    )
    system = f"""你是{platform_name}选题策划,为用户生成 5 个可执行的选题方案。

选题公式 =【对标博主的选题方法】×【我的账号读者最关心的问题】×【用户这次的意图】。
{rules}

{output_schema(render_schema(TopicIdeas))}"""
    prompt = f"""<my_audience>
我的账号读者最关心的问题(受众需求):
{_render_audience_for_topic(audience)}
</my_audience>

<intent>
用户这次的意图:
{intent_block}
</intent>

<benchmark>
对标博主:{blogger.display_name}(领域:{blogger.niche or "未标注"})
蒸馏 Skill(只学方法,不搬题材):
{skill.skill_markdown[:10000]}
</benchmark>

据 <benchmark> 的选题方法,落到 <my_audience> 的真实需求、收敛到 <intent>,产出 5 个选题,只输出 JSON。"""
    result = create_json_response(settings=settings, prompt=prompt, system=system)
    # typed return:一个 Pydantic 模型驱动「给模型的 schema(render_schema) + 这里的解析校验」,单一源。
    parsed = TopicIdeas.model_validate(result if isinstance(result, dict) else {})
    ideas = [idea for idea in parsed.ideas if idea.title and idea.angle][:5]
    if not ideas:
        raise AIServiceError("AI 返回的选题方案为空")
    logger.info("%s选题方案生成完成：skill_id=%s，数量=%s", platform_name, skill.id, len(ideas))
    return [idea.model_dump() for idea in ideas]


def _my_account_audience(db: Session, tenant_id: int, my_blogger_id: int | None) -> dict[str, Any] | None:
    """取「我的账号」的受众需求(读者最常问),作选题的真实需求锚点;缺账号/越权/无数据均返回 None(降级不挡路)。"""
    if not my_blogger_id:
        return None
    mine = db.get(BloggerProfile, my_blogger_id)
    if not mine or mine.tenant_id != tenant_id:
        return None
    return parse_audience(mine.attribution_json)


def _render_audience_for_topic(audience: dict[str, Any] | None) -> str:
    """把受众需求渲染进选题 prompt;无数据 → 明确降级说明,禁止 LLM 凭空编造读者需求。"""
    if not audience:
        return "（暂无「我的账号」受众数据：本次仅凭对标博主的选题方法 + 用户填写的意图出选题，不要凭空编造读者需求。）"
    questions = [str(q.get("theme") or "").strip() for q in (audience.get("questions") or []) if isinstance(q, dict)]
    questions = [q for q in questions if q][:6]
    focus = [str(f).strip() for f in (audience.get("focus_points") or []) if str(f).strip()][:6]
    lines = "\n".join(f"· {q}" for q in questions) if questions else "（无明确高频问题）"
    out = f"读者反复在问（按热度归纳）：\n{lines}"
    if focus:
        out += f"\n高频关注点：{'、'.join(focus)}"
    return out


def generate_package_content(
    db: Session,
    settings: Settings,
    tenant_id: int,
    blogger: BloggerProfile,
    skill: BloggerSkill,
    payload: XhsPublishPackageCreate,
    task_id: str | None = None,
) -> tuple[dict[str, Any], Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """用创作 agent 跑「生成→自检→修订」循环,收敛后做对标对比与限流词残留扫描。

    返回 (生成稿, 合成轨迹, 对标对比, 质量评分, 合规结果)。
    """
    benchmark_stats, distillation = _load_report(db, skill)
    ctx = CreationContext(
        blogger=blogger,
        skill=skill,
        payload=payload,
        platform=blogger.platform,
        content_type=payload.content_type,
        benchmark_stats=benchmark_stats,
        distillation=distillation,
        my_video_baseline=_load_my_video_baseline(db, tenant_id, getattr(payload, "my_account_id", None)),
        extra_block_words=_load_extra_block_words(db),
        compliance_enabled=settings.creation_compliance_enabled,
    )
    agent = build_creation_agent(settings, ctx)

    on_event = None
    if task_id:
        def on_event(kind: str, event: dict[str, Any]) -> None:
            triple = humanize_event(kind, event, subject="内容", gerund="起草")
            if triple:
                step, status, message = triple
                record_task_event(db, tenant_id, task_id, step, status, message)

    generated, trace = run_agent(settings, agent, ctx, on_event=on_event)

    # 收敛后再扫一次限流词,把残留(若预算耗尽仍有)标注给用户。
    compliance: dict[str, Any] = {"enabled": ctx.compliance_enabled, "passed": True, "hits": []}
    if ctx.compliance_enabled:
        niche = getattr(ctx.blogger, "niche", "") or ""
        compliance = scan_creation(generated, ctx.platform, niche=niche, extra_words=ctx.extra_block_words).creation_dict()
        hits = compliance["hits"]
        if task_id:
            if hits:
                record_task_event(db, tenant_id, task_id, "平台合规", "running", f"已尽力规避,还有 {len(hits)} 个限流词建议手动调整")
            else:
                record_task_event(db, tenant_id, task_id, "平台合规", "running", "内容已规避平台限流词")

    if task_id:
        record_task_event(db, tenant_id, task_id, "对标对比", "running", "正在和对标博主比对差距…")
    model = (settings.distill_text_model or "").strip() or None
    benchmark = build_benchmark_comparison(settings, generated, ctx, model)
    quality = evaluate_creation_quality(generated, ctx)
    return generated, trace, benchmark, quality, compliance


def _load_my_video_baseline(db: Session, tenant_id: int, my_account_id: int | None) -> dict[str, Any]:
    """取「我的账号」视频笔记的拍法基线(video_profile 汇总),供视频创作把对标拍法降维到用户做得到的版本。

    缺账号/越权/非「我的账号」/无视频档案 → 空(降级不挡路)。
    """
    if not my_account_id:
        return {}
    mine = db.get(BloggerProfile, my_account_id)
    if not mine or mine.tenant_id != tenant_id or mine.account_type != "mine":
        return {}
    posts = db.scalars(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == my_account_id,
            BloggerPost.content_type == "video",
            BloggerPost.status == "active",
        )
    ).all()
    profiles: list[dict[str, Any]] = []
    for post in posts:
        raw = (post.video_profile or "").strip()
        if not raw:
            continue
        try:
            prof = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(prof, dict) and prof:
            profiles.append(prof)
    return summarize_video_baseline(profiles)


def _load_extra_block_words(db: Session) -> list[str]:
    """从 AppSetting(key=compliance_extra_words,JSON 数组)读租户自定义限流词;缺省空。"""
    setting = db.get(AppSetting, "compliance_extra_words")
    if not setting or not setting.value:
        return []
    try:
        words = json.loads(setting.value)
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(w).strip() for w in words if isinstance(words, list) and str(w).strip()]


def _load_report(db: Session, skill: BloggerSkill) -> tuple[dict[str, Any], dict[str, Any]]:
    """从该 Skill 对应蒸馏 run 的 report_json 取 (统计画像 stats, 结构化蒸馏 distillation)。缺则各空。"""
    run = db.get(BloggerDistillationRun, skill.run_id)
    if not run or not run.report_json:
        return {}, {}
    try:
        report = json.loads(run.report_json)
    except (json.JSONDecodeError, TypeError):
        return {}, {}
    if not isinstance(report, dict):
        return {}, {}
    stats = report.get("stats") if isinstance(report.get("stats"), dict) else {}
    distillation = report.get("distillation") if isinstance(report.get("distillation"), dict) else {}
    return stats, distillation


