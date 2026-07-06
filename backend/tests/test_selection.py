"""建档升详情选片(中位数 + 最近 + 动态 K 爆文保底,纯函数)。"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.blogger_distillation.service.selection import hot_guarantee_count, select_detail_targets


@dataclass
class _C:
    like_count: int = 0
    favorite_count: int = 0
    published_at: datetime | None = None


def _dt(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=timezone.utc)


def _sel(items, *, total, limit, floor=3):
    return select_detail_targets(items, total=total, limit=limit, hot_ratio=0.03, hot_floor=floor, hot_cap=12)


def test_hot_guarantee_count_dynamic_clamp():
    assert hot_guarantee_count(0, ratio=0.03, floor=3, cap=12) == 0
    assert hot_guarantee_count(50, ratio=0.03, floor=3, cap=12) == 3  # round(1.5)=2 → 抬到 floor 3
    assert hot_guarantee_count(300, ratio=0.03, floor=3, cap=12) == 9
    assert hot_guarantee_count(1000, ratio=0.03, floor=3, cap=12) == 12  # 封顶


def test_prefers_recent_above_median():
    high_recent = [_C(1000, 500, _dt(2026, 1, i + 1)) for i in range(5)]  # eng 1500
    low_old = [_C(10, 5, _dt(2025, 1, i + 1)) for i in range(5)]  # eng 15
    res = _sel([*low_old, *high_recent], total=10, limit=5, floor=1)
    assert set(map(id, res)) == set(map(id, high_recent))  # 只取高赞近期那 5 篇


def test_hot_bang_guaranteed_regardless_of_age():
    old_bang = _C(100000, 50000, _dt(2020, 1, 1))  # 很老但巨爆
    recent = [_C(100, 50, _dt(2026, 1, i + 1)) for i in range(20)]
    res = _sel([*recent, old_bang], total=21, limit=5)  # total=21 → K=3
    assert any(c is old_bang for c in res)  # 老爆文靠保底进来
    assert len(res) == 5


def test_limit_respected_and_filled():
    items = [_C(10, 5, _dt(2026, 1, i + 1)) for i in range(8)]  # 同赞,全部 ≥ 中位数
    res = _sel(items, total=8, limit=5, floor=1)
    assert len(res) == 5


def test_fills_below_median_when_not_enough_above():
    high = [_C(1000, 0, _dt(2026, 1, i + 1)) for i in range(6)]  # eng 1000
    low = [_C(1, 0, _dt(2025, 1, i + 1)) for i in range(4)]  # eng 1(中位数 500.5 → 低于)
    res = _sel([*high, *low], total=10, limit=8, floor=1)
    assert len(res) == 8  # 上位不够,按时间补到 limit
    assert all(any(h is r for r in res) for h in high)  # 6 篇高赞都在


def test_empty_and_zero_limit():
    assert _sel([], total=0, limit=5) == []
    assert _sel([_C(10, 5, _dt(2026, 1, 1))], total=1, limit=0) == []
