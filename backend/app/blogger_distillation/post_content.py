"""笔记 →「可学文本」的统一装配。

历史上各功能各自拼 body_text + transcript_text(analysis / account_audit …)。
这里收口成一处:一篇笔记的完整可学文本 = 标题 + 正文 + 口播/字幕 + 图内文字(逐张带
「第N张」标签);外加一个紧凑的"视觉"块(封面话术/版式/风格/逐张说明)。新增模态(如视频
关键帧文字)只改这一个文件,蒸馏/对标/诊断即自动受益。
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
    """从 visual_digest 拼一个紧凑的"视觉"块,供 prompt 追加;无视觉信息则空串。

    新形态:封面/版式/风格 + 逐张(第N张·角色·一句话说明);旧形态兜底 info_points 数组。
    """
    digest = visual_digest_dict(post)
    if not digest:
        return ""
    lines: list[str] = []
    hook = str(digest.get("cover_hook") or "").strip()
    layout = str(digest.get("layout") or "").strip()
    style = str(digest.get("style") or "").strip()
    if hook:
        lines.append(f"封面文案：{hook}")
    if layout:
        lines.append(f"版式：{layout}")
    if style:
        lines.append(f"视觉风格：{style}")
    images = digest.get("images")
    if isinstance(images, list) and images:
        for im in images:
            if not isinstance(im, dict):
                continue
            role = str(im.get("role") or "").strip()
            desc = str(im.get("desc") or "").strip()
            if not role and not desc:
                continue
            idx = im.get("index")
            label = f"第{idx}张" if idx else "图"
            if role:
                label += f"（{role}）"
            lines.append(f"{label}：{desc}" if desc else label)
    else:
        # 旧形态兜底:info_points 数组。
        points = digest.get("info_points")
        if isinstance(points, list) and points:
            joined = "；".join(str(p).strip() for p in points[:6] if str(p).strip())
            if joined:
                lines.append(f"图片信息点：{joined}")
    return "\n".join(lines).strip()


def has_visual(post: Any) -> bool:
    return bool((getattr(post, "image_text", "") or "").strip() or visual_digest_dict(post))
