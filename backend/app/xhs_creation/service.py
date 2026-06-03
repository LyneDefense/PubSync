import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import BloggerProfile, BloggerSkill, XhsPublishPackage
from app.schemas import XhsPublishPackageCreate, XhsTopicIdeaRequest
from app.services.ai_service import AIServiceError, create_json_response, generate_image, is_ai_enabled


logger = logging.getLogger(__name__)

CONTENT_TYPE_LABELS = {
    "text_note": "图文笔记",
    "image_note": "图文笔记加配图",
    "spoken_script": "口播脚本",
    "video_script": "视频脚本",
}


def create_xhs_publish_package(
    db: Session,
    settings: Settings,
    tenant_id: int,
    payload: XhsPublishPackageCreate,
) -> XhsPublishPackage:
    skill = db.get(BloggerSkill, payload.skill_id)
    if not skill or skill.tenant_id != tenant_id or skill.status != "active":
        raise ValueError("Skill 不存在或不可用")
    blogger = db.get(BloggerProfile, skill.blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("Skill 对应的博主不存在")
    if payload.content_type == "image_note" and payload.image_count_mode == "manual" and not payload.requested_image_count:
        raise ValueError("手动配图数量至少为 1")
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")

    logger.info(
        "小红书发布包生成开始：租户=%s，博主=%s，skill_id=%s，类型=%s，主题=%s",
        tenant_id,
        blogger.display_name,
        skill.id,
        payload.content_type,
        payload.topic,
    )
    generated = generate_package_content(settings, blogger, skill, payload)
    image_plan = normalize_image_plan(generated.get("image_plan"))
    image_urls: list[str] = []
    error_message: str | None = None

    if payload.content_type == "image_note":
        target_count = resolve_image_count(payload, generated, image_plan)
        image_plan = image_plan[:target_count]
        if target_count and not image_plan:
            image_plan = build_fallback_image_plan(generated, target_count)
        for index, item in enumerate(image_plan, start=1):
            prompt = str(item.get("prompt") or "").strip()
            if not prompt:
                continue
            try:
                image_url = generate_image(settings, prompt, f"xhs-package-{skill.id}-{index}")
                if image_url:
                    image_urls.append(image_url)
            except Exception as exc:  # noqa: BLE001 - keep the package usable if image generation fails.
                logger.warning("小红书发布包配图生成失败：skill_id=%s，序号=%s，错误=%s", skill.id, index, exc)
                error_message = f"部分配图生成失败：{exc}"

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
        title=str(generated.get("title") or "").strip(),
        body_text=str(generated.get("body_text") or "").strip(),
        hashtags_json=json.dumps(normalize_string_list(generated.get("hashtags")), ensure_ascii=False),
        cover_text=str(generated.get("cover_text") or "").strip(),
        image_plan_json=json.dumps(image_plan, ensure_ascii=False),
        image_urls_json=json.dumps(image_urls, ensure_ascii=False),
        script_json=json.dumps(normalize_script(generated.get("script"), payload.content_type), ensure_ascii=False),
        status="generated",
        error_message=error_message,
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    logger.info("小红书发布包生成完成：package_id=%s，图片=%s", package.id, len(image_urls))
    return package


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

    logger.info(
        "小红书选题方案生成开始：租户=%s，博主=%s，skill_id=%s，种子主题=%s",
        tenant_id,
        blogger.display_name,
        skill.id,
        payload.seed_topic,
    )
    prompt = f"""
你是小红书选题策划。请基于“博主蒸馏 Skill”为用户生成 5 个可执行的选题方案。

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
    logger.info("小红书选题方案生成完成：skill_id=%s，数量=%s", skill.id, len(normalized))
    return normalized[:5]


def generate_package_content(
    settings: Settings,
    blogger: BloggerProfile,
    skill: BloggerSkill,
    payload: XhsPublishPackageCreate,
) -> dict[str, Any]:
    content_type_label = CONTENT_TYPE_LABELS.get(payload.content_type, payload.content_type)
    image_instruction = (
        "如果内容类型是图文笔记加配图，请决定 suitable_image_count，范围 1-9。"
        if payload.image_count_mode == "auto"
        else f"如果内容类型是图文笔记加配图，必须规划 {payload.requested_image_count or 1} 张配图。"
    )
    prompt = f"""
你是小红书内容主编。请基于“博主蒸馏 Skill”生成一个可人工发布的小红书发布包。

重要边界：
- 只能学习 Skill 中的结构、节奏、表达方法，不要冒充原博主，不要复制原文。
- 内容必须围绕用户给定主题，不能编造专业事实；不确定的信息要用温和表达。
- 适合小红书：标题要具体，正文要分段，标签要可用，结尾要有轻量互动引导。
- 输出必须是合法 JSON，不要 Markdown，不要解释文字。
- {image_instruction}
- 生成图片 prompt 时不要出现真实人物姓名、真人肖像、logo、品牌标识、平台 UI 截图；使用干净、生活化、可商用的概念图或场景图。

创作输入：
{json.dumps({
        "blogger": {
            "display_name": blogger.display_name,
            "niche": blogger.niche,
            "description": blogger.description,
        },
        "content_type": payload.content_type,
        "content_type_label": content_type_label,
        "topic": payload.topic,
        "target_audience": payload.target_audience,
        "content_goal": payload.content_goal,
        "keywords": payload.keywords,
        "image_count_mode": payload.image_count_mode,
        "requested_image_count": payload.requested_image_count,
    }, ensure_ascii=False, indent=2)}

博主蒸馏 Skill：
{skill.skill_markdown[:12000]}

输出 JSON 字段：
{{
  "title": "小红书标题，最多 28 个汉字",
  "body_text": "可直接复制的小红书正文。图文笔记用正文；脚本类型也要给一段发布说明。",
  "hashtags": ["话题标签，不要带#号"],
  "cover_text": "封面文案，最多 18 个汉字",
  "suitable_image_count": 0,
  "image_plan": [
    {{
      "slot": 1,
      "purpose": "这张图的作用",
      "caption": "图上可以放的短文案",
      "prompt": "English image generation prompt"
    }}
  ],
  "script": {{
    "duration_seconds": 0,
    "segments": [
      {{
        "start": "0s",
        "end": "5s",
        "scene": "画面/镜头建议",
        "voiceover": "口播或旁白",
        "subtitle": "屏幕字幕"
      }}
    ],
    "shooting_notes": ["拍摄建议"]
  }}
}}
"""
    return create_json_response(settings=settings, prompt=prompt)


def normalize_topic_idea(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(item.get("title") or "").strip(),
        "angle": str(item.get("angle") or "").strip(),
        "target_audience": str(item.get("target_audience") or "").strip(),
        "content_goal": str(item.get("content_goal") or "").strip(),
        "keywords": normalize_string_list(item.get("keywords")),
        "reason": str(item.get("reason") or "").strip(),
    }


def resolve_image_count(payload: XhsPublishPackageCreate, generated: dict[str, Any], image_plan: list[dict[str, Any]]) -> int:
    if payload.image_count_mode == "manual":
        return clamp_int(payload.requested_image_count or 1, 1, 9)
    raw_count = generated.get("suitable_image_count")
    if raw_count is None:
        raw_count = len(image_plan) or 3
    return clamp_int(raw_count, 1, 9)


def normalize_image_plan(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "slot": clamp_int(item.get("slot") or index, 1, 9),
                "purpose": str(item.get("purpose") or "").strip(),
                "caption": str(item.get("caption") or "").strip(),
                "prompt": str(item.get("prompt") or "").strip(),
            }
        )
    return result


def build_fallback_image_plan(generated: dict[str, Any], target_count: int) -> list[dict[str, Any]]:
    title = str(generated.get("title") or "xiaohongshu lifestyle note")
    return [
        {
            "slot": index,
            "purpose": "补充正文视觉层次",
            "caption": title[:18],
            "prompt": (
                "Clean Xiaohongshu lifestyle editorial image, soft natural light, practical knowledge sharing scene, "
                "warm composition, no human face, no celebrity, no logo, no brand mark, no UI screenshot, no text"
            ),
        }
        for index in range(1, target_count + 1)
    ]


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip().lstrip("#")
        if text and text not in result:
            result.append(text)
    return result[:12]


def normalize_script(value: Any, content_type: str) -> dict[str, Any]:
    if isinstance(value, dict):
        script = dict(value)
    else:
        script = {}
    if content_type not in {"spoken_script", "video_script"}:
        return script if script.get("segments") else {}
    segments = script.get("segments")
    if not isinstance(segments, list):
        script["segments"] = []
    notes = script.get("shooting_notes")
    if not isinstance(notes, list):
        script["shooting_notes"] = []
    return script


def clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))
