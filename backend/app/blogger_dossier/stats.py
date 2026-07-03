"""账号事实统计(档案②数据层):从**全量笔记池**算,不从蒸馏样本算。

发布节奏 / 成长趋势属于账号事实,从快照子集算必失真(挑高赞 50 篇算出的"更新间隔"不是真节奏),
故从 :mod:`app.blogger_distillation.analysis` 移到这里;蒸馏 stats 不再产出它们。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.blogger_distillation.analysis import analyze_by_modality, modality_comparison
from app.models import BloggerPost


def account_stats(posts: list[BloggerPost]) -> dict[str, Any]:
    """账号级数据面板。posts 应为在架笔记(调用方过滤 excluded/delisted)。"""
    n = len(posts)
    if not n:
        return {"note_count": 0}
    total_like = sum(p.like_count or 0 for p in posts)
    total_fav = sum(p.favorite_count or 0 for p in posts)
    # 互动率(赞藏评÷浏览量)已下线:小红书不公开浏览量,view_count 恒 0 → 永远算不出,不留空指标。
    top = sorted(posts, key=lambda p: p.like_count or 0, reverse=True)[:5]
    return {
        "note_count": n,
        "full_count": sum(1 for p in posts if p.detail_level == "full"),
        "list_count": sum(1 for p in posts if p.detail_level != "full"),
        "average_like": round(total_like / n, 1),
        "average_favorite": round(total_fav / n, 1),
        "average_comment": round(sum(p.comment_count or 0 for p in posts) / n, 1),
        "favorite_like_ratio": round(total_fav / max(total_like, 1), 4),
        "by_modality": analyze_by_modality(posts),
        "modality_comparison": modality_comparison(analyze_by_modality(posts)),
        "frequency_info": analyze_posting_frequency(posts),
        "growth_trend": analyze_growth_trend(posts),
        "top_posts": [
            {"post_id": p.id, "external_id": p.external_id, "title": p.title, "like_count": p.like_count,
             "published_at": p.published_at.isoformat() if p.published_at else None}
            for p in top
        ],
    }


def analyze_posting_frequency(posts: list[BloggerPost]) -> dict[str, Any]:
    """真实发布节奏(需全量数据;从蒸馏 analysis 移入)。"""
    dates = sorted([item.published_at for item in posts if item.published_at is not None])
    if len(dates) < 2:
        return {"pattern": "时间数据不足", "avg_days_between": None}
    intervals = []
    for index in range(1, len(dates)):
        intervals.append(max((dates[index] - dates[index - 1]).total_seconds() / 86400, 0))
    avg_days = round(sum(intervals) / max(len(intervals), 1), 1)
    if avg_days <= 1.5:
        pattern = "高频日更"
    elif avg_days <= 4:
        pattern = "稳定周更多次"
    elif avg_days <= 10:
        pattern = "低频但持续"
    else:
        pattern = "更新间隔较长"
    return {"pattern": pattern, "avg_days_between": avg_days}


def analyze_growth_trend(posts: list[BloggerPost]) -> dict[str, Any]:
    """前后半程互动对比的粗趋势(需全量数据;从蒸馏 analysis 移入)。"""
    dated = sorted([item for item in posts if item.published_at is not None], key=lambda item: item.published_at or datetime.min)
    if len(dated) < 8:
        return {"summary": "样本或时间数据不足，暂不判断趋势"}
    midpoint = len(dated) // 2
    early = dated[:midpoint]
    recent = dated[midpoint:]
    early_avg = sum(item.score for item in early) / max(len(early), 1)
    recent_avg = sum(item.score for item in recent) / max(len(recent), 1)
    delta = round((recent_avg - early_avg) / max(early_avg, 1) * 100, 1)
    return {
        "early_count": len(early),
        "recent_count": len(recent),
        "early_avg_score": round(early_avg, 1),
        "recent_avg_score": round(recent_avg, 1),
        "score_delta_pct": delta,
        "summary": "近期互动走强" if delta > 20 else ("近期互动走弱" if delta < -20 else "近期互动基本平稳"),
    }
