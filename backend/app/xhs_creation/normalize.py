"""创作产物的纯归一化/裁剪工具（无副作用、无 IO）。

从 service.py 抽出,供 service 与 agent.guide 共用,避免 service↔agent 循环依赖。
"""

from __future__ import annotations

from typing import Any

CONTENT_TYPE_LABELS = {
    "text_note": "纯文字笔记",
    "image_note": "图文笔记加配图",
    "spoken_script": "口播脚本",
    "video_script": "视频脚本",
}


def social_platform_name(platform: str) -> str:
    return "抖音" if platform == "douyin" else "小红书"


def clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip().lstrip("#")
        if text and text not in result:
            result.append(text)
    return result[:12]


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
                "format": str(item.get("format") or "").strip(),  # 版式/画幅建议(竖版3:4·封面/步骤图…)
                "prompt": str(item.get("prompt") or "").strip(),
            }
        )
    return result


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


def resolve_image_count(image_count_mode: str, requested_image_count: int | None, generated: dict[str, Any], image_plan: list[dict[str, Any]]) -> int:
    if image_count_mode == "manual":
        return clamp_int(requested_image_count or 1, 1, 9)
    raw_count = generated.get("suitable_image_count")
    if raw_count is None:
        raw_count = len(image_plan) or 3
    return clamp_int(raw_count, 1, 9)


def build_fallback_image_plan(generated: dict[str, Any], target_count: int) -> list[dict[str, Any]]:
    title = str(generated.get("title") or "生活方式分享笔记")
    return [
        {
            "slot": index,
            "purpose": "补充正文视觉层次",
            "caption": title[:18],
            "format": "竖版 3:4" + ("（封面）" if index == 1 else ""),
            "prompt": (
                "干净清爽的生活方式风格配图,自然柔光,贴近实用知识分享的场景,暖色调构图;"
                "不出现真人面孔、名人、logo、品牌标识、平台 UI 截图,画面不带文字"
            ),
        }
        for index in range(1, target_count + 1)
    ]
