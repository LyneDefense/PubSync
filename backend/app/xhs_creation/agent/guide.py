from __future__ import annotations

import json
from typing import Any

from app.blogger_distillation.modality import coarse_modality
from app.compliance import detect_verticals, prompt_guidance
from app.prompts import anti_injection
from app.xhs_creation.agent.content_types import BASE_SCHEMA, CONTENT_TYPE_SPECS
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.creation_kit import build_creation_kit
from app.xhs_creation.agent.platforms import PLATFORM_SPECS
from app.xhs_creation.my_baseline import render_baseline_line
from app.xhs_creation.normalize import normalize_image_plan, normalize_script, normalize_string_list

# 创作内容类型 → 粗模态(image/video),用于挑同形态的对标爆文做示例。
_CT_TO_COARSE = {"text_note": "image", "image_note": "image", "spoken_script": "video", "video_script": "video"}
# 需要「可执行度对齐」的视频类创作(把对标拍法降维到用户做得到的版本)。
_VIDEO_CONTENT_TYPES = {"spoken_script", "video_script"}


def _compliance_block(ctx: CreationContext) -> str:
    if not ctx.compliance_enabled:
        return ""
    verticals = detect_verticals(getattr(ctx.blogger, "niche", "") or "")  # 按赛道给更贴切的规避说明
    return (
        "\n平台限流词规避(这些词会被平台限流/违禁,标题、正文、标签、封面、脚本里都不要出现):\n"
        f"{prompt_guidance(ctx.platform, verticals)}\n"
    )


def _hot_examples_block(ctx: CreationContext, limit: int = 3) -> str:
    """给几条对标博主真实爆文做 few-shot(标题｜互动｜开头片段｜标签),优先同形态。

    只借鉴选题角度/标题结构/开头钩子/节奏——严禁照抄标题、正文、个人经历或搬运其事实。
    数据取自该 Skill 蒸馏 run 的 report.stats.hot_posts,无则返回空串(不挡路)。
    """
    hot = ctx.benchmark_stats.get("hot_posts") if isinstance(ctx.benchmark_stats, dict) else None
    if not isinstance(hot, list) or not hot:
        return ""
    posts = [p for p in hot if isinstance(p, dict)]
    want = _CT_TO_COARSE.get(ctx.content_type, "image")
    same = [p for p in posts if coarse_modality(str(p.get("content_type") or "")) == want]
    picked = (same or posts)[:limit]
    if not picked:
        return ""
    lines: list[str] = []
    for index, post in enumerate(picked, 1):
        title = str(post.get("title") or "").strip() or "（无标题）"
        like = int(post.get("like_count") or 0)
        fav = int(post.get("favorite_count") or 0)
        excerpt = str(post.get("body_excerpt") or "").strip().replace("\n", " ")[:120]
        tags = [str(t).strip() for t in (post.get("hashtags") or []) if str(t).strip()][:4]
        line = f"{index}. 【{like}赞·{fav}藏】{title}"
        if excerpt:
            line += f"\n   开头/正文片段：{excerpt}"
        if tags:
            line += f"\n   标签：{' '.join(tags)}"
        lines.append(line)
    return (
        "<benchmark_examples>\n对标博主真实爆文示例(只借鉴选题角度、标题结构、开头钩子、节奏；"
        "严禁照抄标题/正文/个人经历,也不要搬运其事实):\n" + "\n".join(lines) + "\n</benchmark_examples>\n"
    )


def _shooting_ability_block(ctx: CreationContext) -> str:
    """可执行度对齐(仅视频):用「我的账号」拍法基线,把对标博主的高阶拍法降维到用户做得到的版本。

    有基线 → 在基线上「进阶一步、但学得会」;无基线 → 按大众可执行条件兜底。图文/纯文字不出此段。
    """
    if ctx.content_type not in _VIDEO_CONTENT_TYPES:
        return ""
    line = render_baseline_line(ctx.my_video_baseline)
    if line:
        body = (
            f"{line}\n"
            "分镜要在这个基线上「进阶一步、但学得会」:别照搬对标博主的高难度运镜/复杂转场——"
            "把对标的拍法降维成用户当前条件拍得出来的版本,并在 shooting_notes 里点明「比你现在多做的那一步」。"
        )
    else:
        body = (
            "(暂无该账号的拍法数据)按大众可执行条件设计:手机拍摄、固定机位或手持、基础剪辑;"
            "分镜要能落地,别堆高难度运镜/复杂转场,把对标博主的拍法降维成新手也拍得出来的版本。"
        )
    return "\n落到我的拍摄条件(学得会的版本,别只给看着爽的):\n" + body + "\n"


def build_creation_system(ctx: CreationContext) -> str:
    """创作的**系统契约**:角色 + 平台口径 + 内容类型指令 + 硬边界 + 合规 + 输出 schema。
    稳定(按 平台×内容类型),不含抓取数据——对标套件/爆文示例在 user,抗其中夹带的指令。"""
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

    return f"""你是{platform.name}内容主编。基于 <benchmark_kit> 里对标博主的方法论,围绕 <creation_input> 的主题,创作一个可人工发布的{platform.name}{spec.label}。

<rules>
- 只能学习方法论里的选题逻辑、结构、节奏、表达方法,产出用户自己的内容;不要冒充原博主、不要复制其原文/原标题/个人经历。
- 必须围绕用户主题,不能编造专业事实;不确定的信息用温和、可求证的表达。
- <benchmark_kit> / <benchmark_examples> 只借鉴其思路、绝不照抄。
- {anti_injection("<benchmark_kit>", "<benchmark_examples>")}
</rules>

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
<output_schema>
只输出下面这个 JSON(字段必须齐全,本类型用不到的字段给空值):
{{
{schema_lines}
}}
</output_schema>"""


def build_creation_prompt(ctx: CreationContext) -> str:
    """创作的**证据(user)**:对标套件 + 真实爆文示例 + 拍法基线 + 用户创作输入。契约在 build_creation_system。"""
    spec = CONTENT_TYPE_SPECS[ctx.content_type]
    payload = ctx.payload

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

    return f"""<benchmark_kit>
{skill_label}:
{skill_block}
</benchmark_kit>
{_hot_examples_block(ctx)}{_shooting_ability_block(ctx)}
<creation_input>
{json.dumps(creation_input, ensure_ascii=False, indent=2)}
</creation_input>

据 <benchmark_kit> 的方法(可参考 <benchmark_examples>),围绕 <creation_input> 创作,按系统消息给定的口径与 JSON 结构输出,只输出该 JSON。"""


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
