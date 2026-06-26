"""博主诊断·硬实力(客观可算,纯函数,无 IO)。

5 维里这 4 维纯算:体量 / 赞藏比 / 爆款力 / 更新活跃(垂直度需模型,见 judge.py)。
口径(详见 docs/对标账号评判_设计.md):
- CES 互动 = 赞×1 + 藏×1 + 评×4(官方思路,评论权重高)。
- 爆文 = 单篇 CES ≥ 该账号 CES 中位数 × 3;爆文率 = 爆文数 / 篇数。
- 赞藏比 = 账号总赞藏 / 粉丝(行业 ≥1.5 算优质)。
所有阈值是默认值,后续可由 config 覆盖。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import median

CES_COMMENT_WEIGHT = 4
HOT_MULTIPLE = 3  # 爆文 = CES ≥ 中位数 × 3


@dataclass
class PostStat:
    """一篇笔记的硬指标(从采集到的 BloggerPost 映射而来)。"""

    likes: int = 0
    collects: int = 0
    comments: int = 0
    published_at: datetime | None = None
    content_type: str = "image"

    @property
    def ces(self) -> int:
        return max(0, self.likes) + max(0, self.collects) + max(0, self.comments) * CES_COMMENT_WEIGHT


@dataclass
class AccountStat:
    """账号级硬指标(从主页资料拿)。"""

    follower_count: int = 0
    note_total: int = 0
    total_like_collect: int = 0


@dataclass
class HardDim:
    key: str
    label: str
    score: int
    detail: str
    metric: dict = field(default_factory=dict)


def _interp(x: float, points: list[tuple[float, float]]) -> float:
    """分段线性插值,两端 clamp。points 按 x 升序的锚点。"""
    pts = sorted(points)
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
            return y0 + t * (y1 - y0)
    return pts[-1][1]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def score_reach(acc: AccountStat) -> HardDim:
    f = max(0, acc.follower_count)
    score = max(0, min(100, round(25 * math.log10(f + 1))))
    tier = "素人(<1k)" if f < 1000 else "KOC(1k–1w)" if f < 10000 else "腰部(1w–10w)" if f < 100000 else "头部(>10w)"
    return HardDim("reach", "体量", score, f"{f} 粉 · {tier}", {"followers": f, "tier": tier})


def score_like_collect_ratio(acc: AccountStat) -> HardDim:
    f = max(1, acc.follower_count)
    ratio = acc.total_like_collect / f
    score = round(_interp(ratio, [(0, 0), (0.5, 40), (1.5, 75), (3, 100)]))
    return HardDim("engagement", "内容穿透·赞藏比", score,
                   f"账号总赞藏/粉丝 = {ratio:.1f}(行业 ≥1.5 算优质)",
                   {"ratio": round(ratio, 2), "total_like_collect": acc.total_like_collect})


def score_viral(posts: list[PostStat]) -> HardDim:
    if not posts:
        return HardDim("viral", "爆款力", 0, "无笔记可算", {})
    ces = [p.ces for p in posts]
    med = median(ces)
    hot = sum(1 for c in ces if med > 0 and c >= med * HOT_MULTIPLE)
    hot_rate = hot / len(posts)
    hot_score = _interp(hot_rate, [(0, 30), (0.1, 60), (0.2, 80), (0.3, 100)])
    med_score = _interp(med, [(0, 0), (500, 50), (2000, 80), (5000, 100)])
    score = round(0.6 * hot_score + 0.4 * med_score)
    return HardDim("viral", "爆款力", score,
                   f"爆文率 {hot_rate:.0%}(互动≥中位×3) · CES互动中位数 {round(med)}",
                   {"hot_rate": round(hot_rate, 3), "ces_median": round(med), "sample": len(posts)})


def score_activity(posts: list[PostStat], now: datetime | None = None) -> HardDim:
    now = _aware(now) if now else datetime.now(timezone.utc)
    dated = sorted(_aware(p.published_at) for p in posts if p.published_at)
    if not dated:
        return HardDim("activity", "更新活跃", 0, "无发布时间可算", {})
    days_since = max(0, (now - dated[-1]).days)
    cutoff = now - timedelta(days=90)
    recent = [d for d in dated if d >= cutoff]
    per_week = len(recent) / (90 / 7)
    freq_score = _interp(per_week, [(0, 0), (1, 50), (3, 90), (7, 100), (14, 70), (30, 40)])
    recency_factor = 1.0 if days_since <= 14 else 0.7 if days_since <= 30 else 0.4 if days_since <= 60 else 0.2
    score = round(freq_score * recency_factor)
    return HardDim("activity", "更新活跃", score,
                   f"近90天 {len(recent)} 篇(约 {per_week:.1f} 篇/周) · 最近更新 {days_since} 天前",
                   {"per_week": round(per_week, 1), "days_since_last": days_since, "recent_90d": len(recent)})


def hard_dimensions(acc: AccountStat, posts: list[PostStat], now: datetime | None = None) -> list[HardDim]:
    """四个可算的硬实力维度(垂直度在 judge.py)。"""
    return [score_reach(acc), score_like_collect_ratio(acc), score_viral(posts), score_activity(posts, now)]
