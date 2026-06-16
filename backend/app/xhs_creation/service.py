import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.blogger_distillation.service.events import record_task_event
from app.compliance import scan_creation_output
from app.config import Settings
from app.models import AppSetting, BloggerDistillationRun, BloggerProfile, BloggerSkill, XhsPublishPackage
from app.schemas import XhsPublishPackageCreate, XhsPublishPackageSave, XhsTopicIdeaRequest
from app.services.ai_service import AIServiceError, create_json_response, generate_image, is_ai_enabled
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
    image_urls: list[str] = []
    error_message: str | None = None

    if payload.content_type == "image_note":
        target_count = resolve_image_count(payload.image_count_mode, payload.requested_image_count, generated, image_plan)
        image_plan = image_plan[:target_count]
        if target_count and not image_plan:
            image_plan = build_fallback_image_plan(generated, target_count)
        if task_id and image_plan:
            record_task_event(db, tenant_id, task_id, "配图", "running", f"正在生成 {len(image_plan)} 张配图…")
        for index, item in enumerate(image_plan, start=1):
            prompt = str(item.get("prompt") or "").strip()
            if not prompt:
                continue
            try:
                image_url = generate_image(settings, prompt, f"{blogger.platform}-package-{skill.id}-{index}")
                if image_url:
                    image_urls.append(image_url)
            except Exception as exc:  # noqa: BLE001 - keep the package usable if image generation fails.
                logger.warning("%s发布包配图生成失败：skill_id=%s，序号=%s，错误=%s", platform_name, skill.id, index, exc)
                error_message = f"部分配图生成失败：{exc}"

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
        "%s发布包草稿生成完成：skill_id=%s，图片=%s，自我修订=%s，质量=%s",
        platform_name,
        skill.id,
        len(image_urls),
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

    package = XhsPublishPackage(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        skill_id=skill.id,
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

    logger.info(
        "%s选题方案生成开始：租户=%s，博主=%s，skill_id=%s，种子主题=%s",
        platform_name,
        tenant_id,
        blogger.display_name,
        skill.id,
        payload.seed_topic,
    )
    prompt = f"""
你是{platform_name}选题策划。请基于“博主蒸馏 Skill”为用户生成 5 个可执行的选题方案。

要求：
- 只学习 Skill 的选题方法、标题结构、切入角度，不要冒充原博主，不要复制原文。
- 如果用户提供了种子主题，所有方案都要围绕该主题变化切角。
- 如果用户没有提供种子主题，请基于 Skill、目标人群和内容目的主动提出可写选题。
- 每个方案要让用户一眼看出：写什么、怎么切、适合谁、为什么值得写。
- 输出必须是合法 JSON，不要 Markdown，不要解释文字。

输入：
{json.dumps({
        "blogger": {
            "display_name": blogger.display_name,
            "niche": blogger.niche,
            "description": blogger.description,
        },
        "seed_topic": payload.seed_topic,
        "target_audience": payload.target_audience,
        "content_goal": payload.content_goal,
        "keywords": payload.keywords,
    }, ensure_ascii=False, indent=2)}

博主蒸馏 Skill：
{skill.skill_markdown[:10000]}

输出 JSON：
{{
  "ideas": [
    {{
      "title": "选题标题，不超过 32 个汉字",
      "angle": "具体切入角度",
      "target_audience": "适合的读者",
      "content_goal": "知识分享/避坑科普/种草转化/观点表达/经验复盘",
      "keywords": ["关键词"],
      "reason": "为什么这个选题值得做"
    }}
  ]
}}
"""
    result = create_json_response(settings=settings, prompt=prompt)
    ideas = result.get("ideas")
    if not isinstance(ideas, list):
        raise AIServiceError("AI 没有返回可用选题方案")
    normalized = [normalize_topic_idea(item) for item in ideas if isinstance(item, dict)]
    normalized = [item for item in normalized if item["title"] and item["angle"]]
    if not normalized:
        raise AIServiceError("AI 返回的选题方案为空")
    logger.info("%s选题方案生成完成：skill_id=%s，数量=%s", platform_name, skill.id, len(normalized))
    return normalized[:5]


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
    benchmark_stats = _load_benchmark_stats(db, skill)
    ctx = CreationContext(
        blogger=blogger,
        skill=skill,
        payload=payload,
        platform=blogger.platform,
        content_type=payload.content_type,
        benchmark_stats=benchmark_stats,
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
        hits = scan_creation_output(generated, ctx.platform, ctx.extra_block_words)
        compliance = {"enabled": True, "passed": not hits, "hits": hits}
        if task_id:
            if hits:
                record_task_event(db, tenant_id, task_id, "平台合规", "running", f"已尽力规避,还有 {len(hits)} 个限流词建议手动调整")
            else:
                record_task_event(db, tenant_id, task_id, "平台合规", "running", "内容已规避平台限流词 ✓")

    if task_id:
        record_task_event(db, tenant_id, task_id, "对标对比", "running", "正在和对标博主比对差距…")
    model = (settings.distill_text_model or "").strip() or None
    benchmark = build_benchmark_comparison(settings, generated, ctx, model)
    quality = evaluate_creation_quality(generated, ctx)
    return generated, trace, benchmark, quality, compliance


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


def _load_benchmark_stats(db: Session, skill: BloggerSkill) -> dict[str, Any]:
    """从该 Skill 对应蒸馏 run 的 report_json 里取回对标博主的统计画像(供对标对比用)。"""
    run = db.get(BloggerDistillationRun, skill.run_id)
    if not run or not run.report_json:
        return {}
    try:
        report = json.loads(run.report_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    stats = report.get("stats") if isinstance(report, dict) else None
    return stats if isinstance(stats, dict) else {}


def normalize_topic_idea(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(item.get("title") or "").strip(),
        "angle": str(item.get("angle") or "").strip(),
        "target_audience": str(item.get("target_audience") or "").strip(),
        "content_goal": str(item.get("content_goal") or "").strip(),
        "keywords": normalize_string_list(item.get("keywords")),
        "reason": str(item.get("reason") or "").strip(),
    }
