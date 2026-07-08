"""我的账号「拍法基线」:从我已采集的视频笔记 video_profile 汇总一个紧凑基线。

用途:创作视频脚本时,把对标博主的高阶拍法「降维到我当前做得到的版本」(可执行度对齐)——
学怎么拍只有在「我拍得出来」时才有用。纯函数、无 IO;随采集层数优雅退化
(只有 L0 → 只出口播浓度;有 L1 → 出镜头数/节奏;有 L2 → 出出镜/画面风格)。
"""

from __future__ import annotations

import statistics
from typing import Any

from app.blogger_distillation.modality import NARRATION_LABELS, ONCAMERA_LABELS, PACE_LABELS


def _dominant(values: list[Any], allowed: dict[Any, str]) -> str:
    """取出现最多的合法枚举值;都不合法则空串。"""
    counts: dict[str, int] = {}
    for v in values:
        key = str(v or "").strip()
        if key in allowed:
            counts[key] = counts.get(key, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else ""


def summarize_video_baseline(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """把一组视频 video_profile 汇总成基线:样本数 / 典型镜头数 / 主导节奏 / 口播浓度 / 是否出镜 / 常见画面风格。"""
    valid = [p for p in profiles if isinstance(p, dict) and p]
    if not valid:
        return {}
    baseline: dict[str, Any] = {"sample_count": len(valid)}

    shots = [int(p["shot_count"]) for p in valid if isinstance(p.get("shot_count"), (int, float))]
    if shots:
        baseline["median_shot_count"] = int(statistics.median(shots))

    pace = _dominant([p.get("pace") for p in valid], PACE_LABELS)
    if pace:
        baseline["pace"] = pace
    narration = _dominant([p.get("narration_level") for p in valid], NARRATION_LABELS)
    if narration:
        baseline["narration_level"] = narration

    oncam = [bool(p["on_camera"]) for p in valid if "on_camera" in p]
    if oncam:
        baseline["on_camera"] = sum(oncam) >= (len(oncam) / 2)  # 过半出镜则记「出镜」

    styles = [str(p.get("shot_style") or "").strip() for p in valid]
    styles = list(dict.fromkeys(s for s in styles if s))[:3]  # 去重、留前 3 个
    if styles:
        baseline["shot_styles"] = styles

    return baseline


def render_baseline_line(baseline: dict[str, Any]) -> str:
    """把基线渲染成给创作 prompt 的一句话;空基线返回 ""。"""
    if not baseline:
        return ""
    parts: list[str] = []
    if baseline.get("median_shot_count"):
        parts.append(f"每条约 {baseline['median_shot_count']} 个镜头")
    if baseline.get("pace") in PACE_LABELS:
        parts.append(PACE_LABELS[baseline["pace"]])
    if baseline.get("narration_level") in NARRATION_LABELS:
        parts.append(NARRATION_LABELS[baseline["narration_level"]])
    if "on_camera" in baseline:
        parts.append(ONCAMERA_LABELS.get(bool(baseline["on_camera"]), ""))
    if baseline.get("shot_styles"):
        parts.append("常见画面:" + "、".join(baseline["shot_styles"]))
    parts = [p for p in parts if p]
    if not parts:
        return ""
    count = baseline.get("sample_count", 0)
    head = f"你的账号目前拍法基线(据你已采集的 {count} 条视频):" if count else "你的账号目前拍法基线:"
    return head + "；".join(parts)
