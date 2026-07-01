"""笔记 →「可学文本」的统一装配。

历史上各功能各自拼 body_text + transcript_text(analysis / rollout / account_audit …)。
这里收口成一处:一篇笔记的完整可学文本 = 标题 + 正文 + 口播/字幕 + 图内文字;外加一个
紧凑的"视觉"块(封面话术/版式/风格/信息点)。新增模态(如视频关键帧文字)只改这一个文件,
蒸馏/SkillOpt/对标/诊断即自动受益。
"""

from __future__ import annotations

import json
from typing import Any


def visual_digest_dict(post: Any) -> dict[str, Any]:
    raw = getattr(post, "visual_digest", "") or ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def assemble_learnable_text(post: Any) -> str:
    """一篇笔记的完整"可学文本":标题 + 正文 + 口播/字幕 + 图内文字。"""
    parts: list[str] = []
    title = (getattr(post, "title", "") or "").strip()
    body = (getattr(post, "body_text", "") or "").strip()
    transcript = (getattr(post, "transcript_text", "") or "").strip()
    image_text = (getattr(post, "image_text", "") or "").strip()
    if title:
        parts.append(title)
    if body:
        parts.append(body)
    if transcript:
        parts.append(transcript)
    if image_text:
        parts.append(f"[图内文字]\n{image_text}")
    return "\n".join(parts).strip()


def visual_context(post: Any) -> str:
    """从 visual_digest 拼一个紧凑的"视觉"块,供 prompt 追加;无视觉信息则空串。"""
    digest = visual_digest_dict(post)
    if not digest:
        return ""
    lines: list[str] = []
    hook = str(digest.get("cover_hook") or "").strip()
    layout = str(digest.get("layout") or "").strip()
    style = str(digest.get("style") or "").strip()
    points = digest.get("info_points")
    if hook:
        lines.append(f"封面文案：{hook}")
    if layout:
        lines.append(f"版式：{layout}")
    if style:
        lines.append(f"视觉风格：{style}")
    if isinstance(points, list) and points:
        joined = "；".join(str(p).strip() for p in points[:6] if str(p).strip())
        if joined:
            lines.append(f"图片信息点：{joined}")
    return "\n".join(lines).strip()


def has_visual(post: Any) -> bool:
    return bool((getattr(post, "image_text", "") or "").strip() or visual_digest_dict(post))
