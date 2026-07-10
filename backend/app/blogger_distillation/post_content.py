"""笔记 →「可学文本」的统一装配。

历史上各功能各自拼 body_text + transcript_text(analysis / account_audit …)。
这里收口成一处:一篇笔记的完整可学文本 = 标题 + 正文 + 口播/字幕 + 图内文字(逐张带
「第N张」标签);外加一个紧凑的"视觉"块(封面话术/版式/风格/逐张说明)。新增模态(如视频
关键帧文字)只改这一个文件,蒸馏/对标/诊断即自动受益。
"""

from __future__ import annotations

import json
from typing import Any

from app.blogger_distillation.modality import VISUAL_VIDEO


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
        # 非口播视频(混剪/卡点/纯 BGM)的转写多是背景音乐歌词/环境音,不是博主口播——
        # 标注降级,别当口播语料喂进蒸馏污染口播车道(口播视频/图文/未知则照旧当正文/口播稿)。
        subtype = (getattr(post, "content_subtype", "") or "").strip()
        if subtype == VISUAL_VIDEO:
            parts.append(f"[字幕/背景音（非口播，仅参考）]\n{transcript}")
        else:
            parts.append(transcript)
    if image_text:
        parts.append(f"[图内文字]\n{image_text}")
    motion = motion_context(post)
    if motion:
        parts.append(f"[视频拍法]\n{motion}")
    return "\n".join(parts).strip()


def motion_context(post: Any) -> str:
    """从 video_profile 拼「视频拍法」块(镜头/节奏/出镜/景别/字幕/转场/风格);无则空串。与 visual_context 对称。"""
    raw = (getattr(post, "video_profile", "") or "").strip()
    if not raw:
        return ""
    try:
        p = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(p, dict):
        return ""
    lines: list[str] = []
    rhythm: list[str] = []
    if p.get("shot_count"):
        rhythm.append(f"{p['shot_count']}个镜头")
    if p.get("cuts_per_min"):
        rhythm.append(f"{p['cuts_per_min']} cuts/min")
    pace = {"fast": "快剪", "medium": "中速", "slow": "慢节奏"}.get(p.get("pace"))
    if pace:
        rhythm.append(pace)
    if rhythm:
        lines.append("节奏：" + "、".join(rhythm))
    if p.get("on_camera") is True:
        lines.append("出镜：真人对镜口播")
    elif p.get("on_camera") is False:
        lines.append("出镜：画外音/无真人出镜")
    for label, key in (("开头3秒", "hook_3s"), ("景别构图", "shot_style"), ("字幕花字", "on_screen_text"), ("转场剪辑", "transitions"), ("拍法概括", "style_summary")):
        val = str(p.get(key) or "").strip()
        if val:
            lines.append(f"{label}：{val}")
    return "\n".join(lines)


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
