"""成长轨迹(档案③轨迹层):内容表现时序 + 爆发点 + 阶段划分。纯函数,只吃 ORM posts。

诚实边界:官方涨粉曲线拿不到,用「笔记互动时序」近似(业内公认爆文曲线≈涨粉曲线);
早期互动低可能只是粉丝基数小,故爆发判定用**相对滚动基线的跃升**,不用绝对值。
"""

from __future__ import annotations

from statistics import median
from typing import Any

from app.models import BloggerPost

MIN_POINTS = 10          # 有时间的笔记少于此数,只给散点、不划阶段(诚实降级)
ROLL_WINDOW = 7          # 滚动基线窗口(取每点之前 N 篇的中位数)
BURST_MULTIPLIER = 3.0   # 爆发判定:赞 ≥ 基线×3 且 ≥ 全局中位×2
LOW_LEVEL = 0.6          # 阶段划分:滚动基线/全局中位 < 0.6 → 低谷
HIGH_LEVEL = 1.6         # > 1.6 → 高位
MIN_SEGMENT = 3          # 阶段最短点数,短段并入前段


def build_trajectory(posts: list[BloggerPost]) -> dict[str, Any]:
    dated = sorted((p for p in posts if p.published_at), key=lambda p: p.published_at)
    points = [
        {
            "post_id": p.id,
            "external_id": p.external_id,
            "date": p.published_at.date().isoformat(),
            "title": (p.title or "")[:30],
            "like": p.like_count or 0,
            "favorite": p.favorite_count or 0,
            "comment": p.comment_count or 0,
            "view": p.view_count or 0,
        }
        for p in dated
    ]
    if len(points) < MIN_POINTS:
        return {
            "points": points, "bursts": [], "phases": [], "recent_trend": "",
            "summary": f"有发布时间的笔记仅 {len(points)} 篇，暂不划分阶段",
        }

    likes = [pt["like"] for pt in points]
    global_med = max(median(likes), 1.0)
    baseline = _rolling_baseline(likes, ROLL_WINDOW, global_med)

    bursts = [
        {"post_id": pt["post_id"], "date": pt["date"], "like": pt["like"], "title": pt["title"]}
        for pt, base in zip(points, baseline)
        if pt["like"] >= BURST_MULTIPLIER * max(base, 1.0) and pt["like"] >= 2 * global_med
    ]
    phases = _segment_phases(points, baseline, global_med)
    recent_trend = _recent_trend(likes, global_med)
    summary = (
        f"{len(points)} 篇有时间线；检测到 {len(bursts)} 个爆发点"
        + (f"（最高 {max(b['like'] for b in bursts)} 赞）" if bursts else "")
        + f"；近期{recent_trend}"
    )
    return {"points": points, "bursts": bursts, "phases": phases, "recent_trend": recent_trend, "summary": summary}


def _rolling_baseline(values: list[int], window: int, fallback: float) -> list[float]:
    """每点的基线 = 它之前 window 篇的中位数;开头样本不足用全局中位兜底。"""
    out: list[float] = []
    for i in range(len(values)):
        prev = values[max(0, i - window):i]
        out.append(float(median(prev)) if len(prev) >= 4 else fallback)
    return out


def _segment_phases(points: list[dict[str, Any]], baseline: list[float], global_med: float) -> list[dict[str, Any]]:
    """按「滚动基线相对全局中位」把时间线切成 低谷/平稳/高位 段;短段并入前段。"""
    labels = []
    for base in baseline:
        ratio = base / global_med
        labels.append("低谷期" if ratio < LOW_LEVEL else ("高位期" if ratio > HIGH_LEVEL else "平稳期"))
    segments: list[list[int]] = []
    for i, label in enumerate(labels):
        if segments and labels[segments[-1][0]] == label:
            segments[-1].append(i)
        else:
            segments.append([i])
    merged: list[list[int]] = []
    for seg in segments:
        if merged and len(seg) < MIN_SEGMENT:
            merged[-1].extend(seg)  # 短段并入前段,避免碎片化
        else:
            merged.append(seg)
    phases = []
    for seg in merged:
        seg_points = [points[i] for i in seg]
        phases.append(
            {
                "label": labels[seg[0]] if len(seg) >= MIN_SEGMENT else "平稳期",
                "start": seg_points[0]["date"],
                "end": seg_points[-1]["date"],
                "note_count": len(seg_points),
                "avg_like": round(sum(p["like"] for p in seg_points) / len(seg_points), 1),
            }
        )
    return phases


def _recent_trend(likes: list[int], global_med: float) -> str:
    recent = likes[-5:]
    ratio = median(recent) / global_med
    if ratio > 1.3:
        return "走强"
    if ratio < 0.7:
        return "走弱"
    return "平稳"
