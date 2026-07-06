"""建档「升详情」选片(纯函数,可单测)。

统一「最新 N 篇 + 历史高赞 M 篇」两批为一套:高赞 + 最近优先,并按笔记总数动态
保底纳入 K 篇爆文(防老爆文被最近挤掉——蒸馏最想学爆文打法)。
调用方已按模态过滤候选;engagement = 赞 + 藏。
"""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Protocol, TypeVar


class _Rankable(Protocol):
    like_count: int
    favorite_count: int
    published_at: datetime | None


T = TypeVar("T", bound=_Rankable)


def _engagement(c: _Rankable) -> int:
    return (c.like_count or 0) + (c.favorite_count or 0)


def hot_guarantee_count(total: int, *, ratio: float, floor: int, cap: int) -> int:
    """爆文保底篇数,随笔记总数动态:clamp(round(total*ratio), floor, cap);total<=0 → 0。"""
    if total <= 0:
        return 0
    return max(floor, min(cap, round(total * ratio)))


def _by_recency(cands: list[T]) -> list[T]:
    """时间新→旧;无发布时间的排最后(避开 tz-aware/naive 混排报错)。"""
    dated = sorted((c for c in cands if c.published_at is not None), key=lambda c: c.published_at, reverse=True)
    return [*dated, *(c for c in cands if c.published_at is None)]


def select_detail_targets(
    need_detail: list[T], *, total: int, limit: int, hot_ratio: float, hot_floor: int, hot_cap: int
) -> list[T]:
    """从「需升详情」候选里选最多 limit 篇升级。

    - 保底:最高赞藏的 K 篇必进(K 随 total 动态,不论发布时间);
    - 其余:赞藏 ≥ 池内中位数 且 时间新→旧优先,不足再按时间补,直到 limit。
    保底爆文计入 limit(最终 ≤ limit 篇)。
    """
    items = list(need_detail)
    if limit <= 0 or not items:
        return []
    k = min(hot_guarantee_count(total, ratio=hot_ratio, floor=hot_floor, cap=hot_cap), len(items), limit)
    hot = sorted(items, key=_engagement, reverse=True)[:k]
    hot_ids = {id(c) for c in hot}
    med = median([_engagement(c) for c in items])
    rest = [c for c in items if id(c) not in hot_ids]
    above = _by_recency([c for c in rest if _engagement(c) >= med])
    below = _by_recency([c for c in rest if _engagement(c) < med])
    return [*hot, *above, *below][:limit]
