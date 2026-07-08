"""创作套件:把蒸馏的 report_json.distillation 装配成「给 LLM 直接照用」的紧凑配方。

和给人读的 skill_markdown 分开——这份是**机器面向**:只取**当前内容类型对应的模态车道** +
内核声音 + 选题原料(选题方法/读者需求)+ 合规红线,对齐创作输出字段(标题/正文/封面/标签/脚本)。
创作时按需装配(读已存的 report_json,无需重蒸;老 skill 无 distillation 时创作端回落 skill_markdown)。
"""

from __future__ import annotations

from typing import Any

from app.blogger_distillation.modality import (
    IMAGE_TEXT,
    VIDEO,
    subtype_label,
)

# lane-collapse 之前的老 skill 车道键(口播/非口播),回落时兼容,不再作为映射目标。
_LEGACY_VIDEO_LANES = ("talking_video", "visual_video")

# 创作内容类型 → 蒸馏内容车道。蒸馏侧已把口播/非口播收敛成一条「视频」车道(话术+拍法),
# 所以口播脚本和视频脚本都读同一份视频车道(拍法方法论);图文/纯文字读图文车道。
_CT_TO_LANE: dict[str, str] = {
    "text_note": IMAGE_TEXT,
    "image_note": IMAGE_TEXT,
    "spoken_script": VIDEO,
    "video_script": VIDEO,
}


def _pick_lane(lanes: dict[str, Any], content_type: str) -> tuple[str, dict[str, Any]]:
    """选当前内容类型对应车道;缺则按「同模态优先(含老 skill 的口播/非口播)」回落到任一有内容的车道。"""
    preferred = _CT_TO_LANE.get(content_type, IMAGE_TEXT)
    if preferred == VIDEO:
        order = (VIDEO, *_LEGACY_VIDEO_LANES, IMAGE_TEXT)
    else:
        order = (IMAGE_TEXT, VIDEO, *_LEGACY_VIDEO_LANES)
    for lane in order:
        if isinstance(lanes.get(lane), dict) and lanes[lane]:
            return lane, lanes[lane]
    for lane, content in lanes.items():
        if isinstance(content, dict) and content:
            return lane, content
    return preferred, {}


def _sec(title: str, items: Any, cap: int = 5) -> str:
    vals = [str(x).strip() for x in (items or []) if str(x).strip()][:cap]
    return f"【{title}】\n" + "\n".join(f"- {v}" for v in vals) if vals else ""


def build_creation_kit(distillation: dict[str, Any] | None, content_type: str) -> str:
    """装配当前内容类型的创作套件。distillation 缺内容层则返回 ""(调用方回落 skill_markdown)。"""
    if not isinstance(distillation, dict):
        return ""
    lanes = distillation.get("content_lanes")
    if not isinstance(lanes, dict) or not lanes:
        return ""
    lane_key, lane = _pick_lane(lanes, content_type)

    voice = distillation.get("voice") if isinstance(distillation.get("voice"), dict) else {}
    angle = distillation.get("angle_layer") if isinstance(distillation.get("angle_layer"), dict) else {}
    blocks: list[str] = []

    glance = str(distillation.get("one_glance") or "").strip()
    if glance:
        blocks.append(f"一句话打法：{glance}")

    vparts: list[str] = []
    if str(voice.get("self_ref") or "").strip():
        vparts.append(f"自称「{str(voice['self_ref']).strip()}」")
    if str(voice.get("tone") or "").strip():
        vparts.append(str(voice["tone"]).strip())
    cps = [str(c).strip() for c in (voice.get("catchphrases") or [])[:5] if str(c).strip()]
    if cps:
        vparts.append("口头禅：" + "、".join(cps))
    if vparts:
        blocks.append("【人设声音（语气/自称要一致）】" + " · ".join(vparts))

    topic_block = "\n".join(
        x for x in (
            _sec("选题方法", angle.get("topic_method"), 4),
            _sec("常用角度", angle.get("topic_angles"), 5),
            _sec("读者最常问（对着真实需求选题）", distillation.get("comment_insights"), 5),
        ) if x
    )
    if topic_block:
        blocks.append(topic_block)

    # 视频车道:把「结构骨架」显式呈现为拍法(分镜/节奏/开头),让创作照这个博主的拍法来,而不是通用模板。
    is_video = lane_key in (VIDEO, *_LEGACY_VIDEO_LANES)
    write_block = "\n".join(
        x for x in (
            _sec("标题公式", lane.get("title_formulas"), 6),
            _sec("开头钩子（前 3 秒留人）" if is_video else "开头模板", lane.get("opening_templates"), 4),
            _sec(
                "拍法·分镜/节奏/开头结构" if is_video else "结构骨架",
                lane.get("body_structures") or lane.get("video_script_structures"),
                6 if is_video else 4,
            ),
            _sec("情绪节奏/留人钩子", lane.get("emotional_rhythm"), 3),
            _sec("封面/首帧文案" if is_video else "封面文案", lane.get("cover_text_rules"), 4),
            _sec("画面/版式" if is_video else "图内编排/版式", lane.get("visual_layout_patterns"), 4),
            _sec("语言 DNA", lane.get("language_dna"), 5),
            _sec("互动/CTA", lane.get("cta_strategy"), 3),
            _sec("标签策略", lane.get("hashtag_strategy"), 3),
        ) if x
    )
    if write_block:
        blocks.append(f"## 写法·{subtype_label(lane_key)}（本次内容形态,直接照用）\n{write_block}")

    bd_lines: list[str] = []
    for b in (lane.get("top_post_breakdowns") or [])[:3]:
        if not isinstance(b, dict):
            continue
        tactic = str(b.get("reusable_tactic") or "").strip()
        why = str(b.get("why_viral") or "").strip()
        if tactic:
            bd_lines.append(f"- {tactic}" + (f"（为什么火：{why}）" if why else ""))
    if bd_lines:
        blocks.append("【爆款可复制技巧】\n" + "\n".join(bd_lines))

    redlines = [str(w).strip() for w in (distillation.get("compliance_watchouts") or []) if str(w).strip()][:6]
    redlines += [str(d).strip() for d in (distillation.get("do_not_do") or []) if str(d).strip()][:3]
    if redlines:
        blocks.append("【红线（这些写法会限流/不该抄——学思路,绝不照抄进标题/正文/标签/封面）】\n" + "\n".join(f"- {r}" for r in redlines))

    return "\n\n".join(blocks)
