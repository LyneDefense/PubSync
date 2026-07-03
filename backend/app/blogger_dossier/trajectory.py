"""成长轨迹(档案③轨迹层):内容表现时序 + 爆发点 + 阶段划分 + 涨粉拐点。纯函数,只吃 ORM posts。

诚实边界:官方涨粉曲线拿不到,用「笔记互动时序」近似——但赞藏替不了涨粉的**量**,只替得了**拐点**:
一次爆发若把**基线永久抬高一个台阶**,就是把流量转成了粉丝(涨粉型);只留孤峰、基线不动的是一次性爆文。

方法:
1. 按发布密度**分桶**(活跃号按月、低频号按季),每桶取中位互动 —— 抹平不规则发布。
2. 桶序列上做**自底向上合并**找"持久台阶"(变点),不用阈值硬切、不套预设模板。
3. 段命名**按形状挣得**(起步/突破/滑坡/成熟/平稳);台阶跳高的边界 = 涨粉拐点。
4. 每段标**波动性**(稳定输出 / 大开大合)。
5. 点数/桶数不够 → 只给散点或整体,不硬划阶段(诚实降级)。
"""

from __future__ import annotations

from statistics import median, pstdev
from typing import Any

from app.models import BloggerPost

MIN_POINTS = 10           # 有时间的笔记少于此,只给散点、不划阶段
MIN_BUCKETS = 4           # 分桶少于此,只给整体趋势、不划阶段
DENSE_INTERVAL_DAYS = 20  # 中位发布间隔 ≤ 此 → 按月分桶,否则按季(低频)
ROLL_WINDOW = 7           # 单篇爆发判定的滚动基线窗口
BURST_MULTIPLIER = 3.0    # 爆发:赞 ≥ 基线×3 且 ≥ 全局中位×2
STEP_UP = 1.5             # 后段/前段 ≥ 此 → 台阶跳高(突破 / 涨粉拐点)
STEP_DOWN = 0.67          # 后段/前段 ≤ 此 → 台阶跌落(滑坡)
MERGE_REL = 0.4           # 相邻段相对差 < 此 → 同一水平,合并
MIN_SEGMENT_NOTES = 3     # 段最少笔记数,不足并入更近的邻段
HIGH_LEVEL = 1.4          # 段中位 ≥ 全局中位×此 → 高位(配低波动 = 成熟期)
HIGH_CV = 0.8             # 变异系数 ≥ 此 → 大开大合,否则稳定输出


def build_trajectory(posts: list[BloggerPost]) -> dict[str, Any]:
    dated = sorted((p for p in posts if p.published_at), key=lambda p: p.published_at)
    points = [
        {
            "post_id": p.id, "external_id": p.external_id,
            "date": p.published_at.date().isoformat(), "title": (p.title or "")[:30],
            "like": p.like_count or 0, "favorite": p.favorite_count or 0,
            "comment": p.comment_count or 0, "view": p.view_count or 0,
        }
        for p in dated
    ]
    if len(points) < MIN_POINTS:
        return _degraded(points, f"有发布时间的笔记仅 {len(points)} 篇，暂不划分阶段")

    likes = [pt["like"] for pt in points]
    global_med = max(median(likes), 1.0)
    baseline = _rolling_baseline(likes, ROLL_WINDOW, global_med)
    bursts = [
        {"post_id": pt["post_id"], "date": pt["date"], "like": pt["like"], "title": pt["title"]}
        for pt, base in zip(points, baseline)
        if pt["like"] >= BURST_MULTIPLIER * max(base, 1.0) and pt["like"] >= 2 * global_med
    ]

    buckets, quarterly = _bucketize(dated)
    granularity = "quarter" if quarterly else "month"
    recent_trend = _recent_trend(likes, global_med)
    if len(buckets) < MIN_BUCKETS:
        out = _degraded(points, f"按{'季' if quarterly else '月'}分桶仅 {len(buckets)} 段，暂只给整体趋势")
        out.update({"bursts": bursts, "buckets": _public_buckets(buckets), "granularity": granularity,
                    "recent_trend": recent_trend, "low_frequency": quarterly})
        return out

    segs = _enforce_min_notes(buckets, _segment_buckets(buckets))
    phases = _label_phases(buckets, segs, global_med)
    level_ups = _level_ups(buckets, segs)
    summary = _summary(phases, level_ups, bursts, quarterly)
    return {
        "points": points, "buckets": _public_buckets(buckets), "bursts": bursts,
        "phases": phases, "level_ups": level_ups, "recent_trend": recent_trend,
        "granularity": granularity, "low_frequency": quarterly, "summary": summary,
    }


def _degraded(points: list[dict[str, Any]], summary: str) -> dict[str, Any]:
    return {"points": points, "buckets": [], "bursts": [], "phases": [], "level_ups": [],
            "recent_trend": "", "granularity": "", "low_frequency": False, "summary": summary}


def _rolling_baseline(values: list[int], window: int, fallback: float) -> list[float]:
    """每点基线 = 之前 window 篇的中位数;开头样本不足用全局中位兜底。用于单篇爆发判定。"""
    out: list[float] = []
    for i in range(len(values)):
        prev = values[max(0, i - window):i]
        out.append(float(median(prev)) if len(prev) >= 4 else fallback)
    return out


def _bucketize(dated: list[BloggerPost]) -> tuple[list[dict[str, Any]], bool]:
    """按发布密度选粒度(月/季),把笔记分桶,每桶取中位互动。返回(桶列表, 是否季度)。"""
    dates = [p.published_at for p in dated]
    intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    quarterly = bool(intervals) and median(intervals) > DENSE_INTERVAL_DAYS
    groups: dict[tuple[int, int], list[BloggerPost]] = {}
    order: list[tuple[int, int]] = []
    for p in dated:
        d = p.published_at
        key = (d.year, (d.month - 1) // 3) if quarterly else (d.year, d.month)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(p)
    buckets: list[dict[str, Any]] = []
    for key in order:
        ps = groups[key]
        note_likes = [p.like_count or 0 for p in ps]
        buckets.append({
            "period": f"{key[0]}Q{key[1] + 1}" if quarterly else f"{key[0]}.{key[1]:02d}",
            "start": min(p.published_at for p in ps).date().isoformat(),
            "end": max(p.published_at for p in ps).date().isoformat(),
            "median_like": float(median(note_likes)),
            "note_count": len(ps),
            "_likes": note_likes,
            "_posts": ps,
        })
    return buckets, quarterly


def _seg_level(buckets: list[dict[str, Any]], seg: list[int]) -> float:
    return float(median([buckets[i]["median_like"] for i in seg]))


def _segment_buckets(buckets: list[dict[str, Any]]) -> list[list[int]]:
    """自底向上合并:反复并掉「相对差最小」的相邻段,直到所有相邻段差异 ≥ MERGE_REL(即只剩真台阶)。"""
    segs: list[list[int]] = [[i] for i in range(len(buckets))]
    while len(segs) > 1:
        best_rel, best_j = None, -1
        for j in range(len(segs) - 1):
            a, b = _seg_level(buckets, segs[j]), _seg_level(buckets, segs[j + 1])
            rel = abs(a - b) / max(a, b, 1.0)
            if best_rel is None or rel < best_rel:
                best_rel, best_j = rel, j
        if best_rel is None or best_rel >= MERGE_REL:
            break
        segs[best_j:best_j + 2] = [segs[best_j] + segs[best_j + 1]]
    return segs


def _enforce_min_notes(buckets: list[dict[str, Any]], segs: list[list[int]]) -> list[list[int]]:
    """段笔记数不足 MIN_SEGMENT_NOTES 的,并入水平更接近的邻段(避免碎片化阶段)。"""
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for j, seg in enumerate(segs):
            if sum(buckets[i]["note_count"] for i in seg) >= MIN_SEGMENT_NOTES:
                continue
            if j == 0:
                segs[0:2] = [segs[0] + segs[1]]
            elif j == len(segs) - 1:
                segs[-2:] = [segs[-2] + segs[-1]]
            else:
                lv = _seg_level(buckets, seg)
                left, right = _seg_level(buckets, segs[j - 1]), _seg_level(buckets, segs[j + 1])
                if abs(lv - left) <= abs(lv - right):
                    segs[j - 1:j + 1] = [segs[j - 1] + seg]
                else:
                    segs[j:j + 2] = [seg + segs[j + 1]]
            changed = True
            break
    return segs


def _label_phases(buckets: list[dict[str, Any]], segs: list[list[int]], global_med: float) -> list[dict[str, Any]]:
    levels = [_seg_level(buckets, seg) for seg in segs]
    phases: list[dict[str, Any]] = []
    for k, seg in enumerate(segs):
        lv = levels[k]
        prev = levels[k - 1] if k > 0 else None
        nxt = levels[k + 1] if k < len(segs) - 1 else None
        if prev is None and nxt is not None and nxt >= STEP_UP * max(lv, 1.0):
            label = "起步期"
        elif prev is not None and lv >= STEP_UP * max(prev, 1.0):
            label = "突破期"
        elif prev is not None and lv <= STEP_DOWN * max(prev, 1.0):
            label = "滑坡期"
        elif lv >= HIGH_LEVEL * global_med:
            label = "成熟期"
        else:
            label = "平稳期"
        seg_likes = [x for i in seg for x in buckets[i]["_likes"]]
        mean = sum(seg_likes) / max(len(seg_likes), 1)
        cv = (pstdev(seg_likes) / mean) if len(seg_likes) > 1 and mean > 0 else 0.0
        phases.append({
            "label": label,
            "start": buckets[seg[0]]["start"],
            "end": buckets[seg[-1]]["end"],
            "note_count": sum(buckets[i]["note_count"] for i in seg),
            "avg_like": round(lv, 1),
            "volatility": "大开大合" if cv >= HIGH_CV else "稳定输出",
        })
    return phases


def _level_ups(buckets: list[dict[str, Any]], segs: list[list[int]]) -> list[dict[str, Any]]:
    """涨粉拐点:段相对前段台阶跳高(≥STEP_UP)的边界,关联该段最高赞笔记作为触发爆文。"""
    levels = [_seg_level(buckets, seg) for seg in segs]
    ups: list[dict[str, Any]] = []
    for k in range(1, len(segs)):
        if levels[k] < STEP_UP * max(levels[k - 1], 1.0):
            continue
        trigger = max((p for i in segs[k] for p in buckets[i]["_posts"]), key=lambda p: p.like_count or 0, default=None)
        ups.append({
            "date": buckets[segs[k][0]]["start"],
            "from_avg": round(levels[k - 1], 1),
            "to_avg": round(levels[k], 1),
            "trigger": None if trigger is None else {
                "post_id": trigger.id, "external_id": trigger.external_id,
                "title": (trigger.title or "")[:30], "like": trigger.like_count or 0,
                "date": trigger.published_at.date().isoformat() if trigger.published_at else "",
            },
        })
    return ups


def _public_buckets(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in b.items() if not k.startswith("_")} for b in buckets]


def _summary(phases: list[dict], level_ups: list[dict], bursts: list[dict], quarterly: bool) -> str:
    parts = [f"{len(phases)} 个阶段"]
    if level_ups:
        parts.append(f"{len(level_ups)} 个涨粉拐点")
    if bursts:
        parts.append(f"{len(bursts)} 个爆发点（最高 {max(b['like'] for b in bursts)} 赞）")
    tail = "；低频账号，阶段为粗判" if quarterly else ""
    return "；".join(parts) + tail


def _recent_trend(likes: list[int], global_med: float) -> str:
    ratio = median(likes[-5:]) / global_med
    return "走强" if ratio > 1.3 else ("走弱" if ratio < 0.7 else "平稳")
