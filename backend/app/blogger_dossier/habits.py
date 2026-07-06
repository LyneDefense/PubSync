"""运营习惯(账号事实模块):从全量池算的"博主怎么运营"行为统计。

事实主体在此(客观、随池重算、与选哪份画像无关);蒸馏层的解读由前端从画像 report 合并附加。
需正文/转写的项(体裁、评论引导)只对详情级笔记算,并给覆盖度,不拿列表级凑数。
评论引导只看**博主自身内容**(标题/正文/口播),不看读者评论;博主回复习惯才看评论里的 is_author。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.blogger_distillation.analysis import analyze_by_modality, modality_comparison
from app.blogger_dossier.stats import analyze_posting_frequency
from app.models import BloggerPost

_WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
_BAND_ORDER = ["清晨", "上午", "午间", "下午", "晚间", "深夜"]

# 清单体:正文里成排的序号/项目符号行。≥3 行即认为清单体。
_LIST_LINE = re.compile(r"^\s*(?:[0-9]{1,2}[.、)）:：]|[①-⑳]|[-•·▪✦●])")
# 博主主动引导互动的话术(出现在博主自己的标题/正文/口播里)。
_GUIDE_PHRASES = (
    "评论区", "扣1", "扣个1", "扣一个", "扣0", "留言告诉我", "评论告诉我", "评论区聊", "评论区见",
    "你怎么看", "你觉得呢", "说说你", "聊聊你", "求点赞", "求关注", "求收藏", "蹲一个", "在线等",
    "评论区扣", "评论区留言", "有需要的扣", "想要的扣",
)


def operating_habits(posts: list[BloggerPost]) -> dict[str, Any]:
    """运营习惯:发布节奏 / 发布时段 / 模态偏好 / 体裁 / 话题标签 / 内容规格 / 评论引导 / 博主回复。

    发布节奏·时段·内容规格从全量池算(行为事实);体裁/评论引导/回复需正文,只对详情级算并给覆盖度。
    """
    if not posts:
        return {}
    detail = [p for p in posts if p.detail_level == "full"]
    return {
        "coverage": {"pool": len(posts), "detail": len(detail)},
        "posting_rhythm": analyze_posting_frequency(posts),
        "posting_time": _posting_time(posts),
        "modality_pref": modality_comparison(analyze_by_modality(posts)),
        "genre": _genre_distribution(detail),
        "hashtag_usage": _hashtag_usage(detail),
        "content_format": _content_format(posts),
        "comment_guide": _comment_guide_ratio(detail),
        "author_reply": _author_reply_habit(detail),
    }


def _beijing(dt: datetime) -> datetime:
    """转北京时间(小红书/抖音都是国内号)。published_at 是 UTC-aware;裸时间当 UTC。"""
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc) + timedelta(hours=8)


def _hour_band(hour: int) -> str:
    if 5 <= hour < 9:
        return "清晨"
    if 9 <= hour < 12:
        return "上午"
    if 12 <= hour < 14:
        return "午间"
    if 14 <= hour < 18:
        return "下午"
    if 18 <= hour < 23:
        return "晚间"
    return "深夜"


def _posting_time(posts: list[BloggerPost]) -> dict[str, Any]:
    """发布时段(全量池,北京时间):周几分布 + 时段分布 + 最常发的周几/时段。"""
    dated = [p for p in posts if p.published_at]
    if len(dated) < 4:
        return {"sample": len(dated), "weekday_counts": [], "band_counts": [], "top_weekday": None, "top_band": None}
    weekday_counts = [0] * 7
    band_counts = {name: 0 for name in _BAND_ORDER}
    for p in dated:
        bj = _beijing(p.published_at)
        weekday_counts[bj.weekday()] += 1
        band_counts[_hour_band(bj.hour)] += 1
    top_wd = max(range(7), key=lambda i: weekday_counts[i])
    top_band = max(_BAND_ORDER, key=lambda n: band_counts[n])
    return {
        "sample": len(dated),
        "weekday_counts": weekday_counts,
        "band_counts": [{"name": n, "count": band_counts[n]} for n in _BAND_ORDER],
        "top_weekday": _WEEKDAYS[top_wd],
        "top_band": top_band,
    }


def _hashtag_usage(detail: list[BloggerPost]) -> dict[str, Any]:
    """话题标签使用(需正文,仅详情级):篇均标签数 + 高频标签。"""
    if not detail:
        return {"avg_per_note": None, "notes_with": 0, "total": 0, "top_tags": []}
    counts: list[int] = []
    freq: dict[str, int] = {}
    for p in detail:
        try:
            raw = json.loads(p.hashtags_json or "[]")
        except (json.JSONDecodeError, TypeError):
            raw = []
        tags = [str(t).strip().lstrip("#") for t in raw if isinstance(raw, list) and str(t).strip()]
        counts.append(len(tags))
        for t in tags:
            freq[t] = freq.get(t, 0) + 1
    top = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:6]
    return {
        "avg_per_note": round(sum(counts) / len(counts), 1) if counts else None,
        "notes_with": sum(1 for c in counts if c > 0),
        "total": len(detail),
        "top_tags": [{"tag": t, "count": c} for t, c in top],
    }


def _content_format(posts: list[BloggerPost]) -> dict[str, Any]:
    """内容规格(全量池,有几算几):图文篇均张数(视觉计数/媒体数)+ 视频平均时长(秒)。"""
    image_counts: list[int] = []
    video_secs: list[float] = []
    for p in posts:
        if p.content_type == "video":
            if p.duration_seconds:
                video_secs.append(p.duration_seconds)
            continue
        n = p.vision_image_count or 0
        if not n:
            try:
                media = json.loads(p.media_urls_json or "[]")
                n = len(media) if isinstance(media, list) else 0
            except (json.JSONDecodeError, TypeError):
                n = 0
        if n:
            image_counts.append(n)
    return {
        "avg_images": round(sum(image_counts) / len(image_counts), 1) if image_counts else None,
        "image_notes": len(image_counts),
        "avg_video_sec": round(sum(video_secs) / len(video_secs)) if video_secs else None,
        "video_notes": len(video_secs),
    }


def _is_listicle(body: str) -> bool:
    hits = sum(1 for line in (body or "").splitlines() if _LIST_LINE.match(line))
    return hits >= 3


def _genre_distribution(detail: list[BloggerPost]) -> dict[str, Any]:
    """体裁:清单体占比(需正文,仅详情级)。"""
    if not detail:
        return {"listicle": 0, "total": 0, "ratio": None}
    listicle = sum(1 for p in detail if _is_listicle(p.body_text or ""))
    return {"listicle": listicle, "total": len(detail), "ratio": round(listicle / len(detail), 3)}


def _comment_guide_ratio(detail: list[BloggerPost]) -> dict[str, Any]:
    """评论引导:博主**自身内容**(标题+正文+口播)里主动引导互动的笔记占比。不看读者评论。"""
    if not detail:
        return {"count": 0, "total": 0, "ratio": None}
    count = 0
    for p in detail:
        text = f"{p.title or ''}\n{p.body_text or ''}\n{p.transcript_text or ''}"
        if any(phrase in text for phrase in _GUIDE_PHRASES):
            count += 1
    return {"count": count, "total": len(detail), "ratio": round(count / len(detail), 3)}


def _author_reply_habit(detail: list[BloggerPost]) -> dict[str, Any]:
    """博主回复习惯:有评论的笔记里,博主本人下场回复的占比(靠评论 is_author)。

    存量评论无 is_author 标记 → 只统计新采到的;replied 恒 ≥0,覆盖度随重采补齐。
    """
    with_comments = 0
    replied = 0
    for p in detail:
        try:
            comments = json.loads(p.comments_json or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        if not comments:
            continue
        with_comments += 1
        if any(isinstance(c, dict) and c.get("is_author") for c in comments):
            replied += 1
    ratio = round(replied / with_comments, 3) if with_comments else None
    return {"replied": replied, "with_comments": with_comments, "ratio": ratio}
