from __future__ import annotations

import json
from typing import Any

from app.compliance import detect_verticals, prompt_guidance
from app.xhs_creation.agent.content_types import BASE_SCHEMA, CONTENT_TYPE_SPECS
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.creation_kit import build_creation_kit
from app.xhs_creation.agent.platforms import PLATFORM_SPECS
from app.xhs_creation.normalize import normalize_image_plan, normalize_script, normalize_string_list


def _compliance_block(ctx: CreationContext) -> str:
    if not ctx.compliance_enabled:
        return ""
    verticals = detect_verticals(getattr(ctx.blogger, "niche", "") or "")  # 按赛道给更贴切的规避说明
    return (
        "\n平台限流词规避(这些词会被平台限流/违禁,标题、正文、标签、封面、脚本里都不要出现):\n"
        f"{prompt_guidance(ctx.platform, verticals)}\n"
    )


def build_creation_prompt(ctx: CreationContext) -> str:
    """组合式创作提示词 = 公共骨架 + 平台片段 + 内容类型片段 + Skill + 创作输入 + 仅该类型输出 schema。"""
    platform = PLATFORM_SPECS[ctx.platform]
    spec = CONTENT_TYPE_SPECS[ctx.content_type]
    payload = ctx.payload

    if ctx.content_type == "image_note":
        if payload.image_count_mode == "auto":
            image_instruction = "请自行决定 suitable_image_count(1-9),并规划相同数量的 image_plan。"
        else:
            image_instruction = f"必须规划 {payload.requested_image_count or 1} 张配图(image_plan 与之数量一致)。"
    else:
        image_instruction = "本类型不需要配图,image_plan 留空数组、suitable_image_count 给 0。"

    schema_lines = BASE_SCHEMA + ("," if spec.schema_fragment else "") + ("\n" + spec.schema_fragment if spec.schema_fragment else "")

    # 优先用「创作套件」(按本次内容形态装配、对齐输出字段、带护栏);老 skill 无结构化蒸馏时回落整篇 skill_markdown。
    creation_kit = build_creation_kit(ctx.distillation, ctx.content_type)
    skill_block = creation_kit or ctx.skill.skill_markdown[:12000]
    skill_label = "对标博主创作套件（已按本次内容形态装配,直接照用）" if creation_kit else "对标博主蒸馏方法论 Skill"

    creation_input = {
        "content_type": ctx.content_type,
        "content_type_label": spec.label,
        "topic": payload.topic,
        "target_audience": payload.target_audience,
        "content_goal": payload.content_goal,
        "keywords": payload.keywords,
    }

    return f"""
你是{platform.name}内容主编。请基于“对标博主蒸馏出的方法论 Skill”,围绕用户给定主题,创作一个可人工发布的{platform.name}{spec.label}。

硬边界:
- 只能学习 Skill 里的选题逻辑、结构、节奏、表达方法,产出用户自己的内容;不要冒充原博主、不要复制其原文/原标题/个人经历。
- 必须围绕用户主题,不能编造专业事实;不确定的信息用温和、可求证的表达。
- 输出必须是合法 JSON 对象,不要 Markdown、不要解释过程、不要 <think>。

{platform.name}创作口径:
- 标题:{platform.title_rule}
- 语气:{platform.tone_rule}
- 互动:{platform.cta_rule}
- 标签:{platform.hashtag_rule}
- 合规:{platform.compliance_note}

本次内容类型:{spec.label}
- {spec.instruction}
- {image_instruction}
{_compliance_block(ctx)}
{skill_label}:
{skill_block}

创作输入:
{json.dumps(creation_input, ensure_ascii=False, indent=2)}

只输出下面这个 JSON(字段必须齐全,本类型用不到的字段给空值):
{{
{schema_lines}
}}
"""


def normalize_creation_output(data: dict[str, Any], ctx: CreationContext) -> dict[str, Any]:
    """对模型返回做确定性清洗,保证 sensors 看到一致结构。"""
    if not isinstance(data, dict):
        data = {}
    data["title"] = str(data.get("title") or "").strip()
    data["body_text"] = str(data.get("body_text") or "").strip()
    data["cover_text"] = str(data.get("cover_text") or "").strip()
    data["hashtags"] = normalize_string_list(data.get("hashtags"))
    data["image_plan"] = normalize_image_plan(data.get("image_plan"))
    data["script"] = normalize_script(data.get("script"), ctx.content_type)
    return data
