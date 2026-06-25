"""泛搜索候选的「规则综合分」——纯函数,不调 LLM,便宜可测。

综合分 = 火爆度 + 命中方向权重 + 活跃 + 个人号偏好 +(有种子时)越像种子越靠前。
火爆度沿用 engine.popularity_score(粉丝+互动);这里只做加权合成与排序。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.benchmark_discovery.engine import popularity_score


@dataclass
class CandidateSignals:
    """一个候选的客观信号(召回阶段收集,喂给打分)。"""

    external_id: str
    follower_count: int = 0
    like_samples: list[int] = field(default_factory=list)
    post_count: int = 0
    active: bool = True               # 近期是否还在更新(取不到默认 True)
    is_personal: bool = True          # 个人号 vs 机构/泛号(取不到默认 True)
    matched_weight: float = 0.0       # 命中的扩展方向的权重之和(0-100 量纲)
    similarity_to_seed: float | None = None  # 0-100,无种子时 None
    popularity_known: bool = True     # 粉丝/互动是否拿得到(搜笔记取的作者拿不到 → False)


# 粉丝数拿不到时给的中性火爆度:别把"内容出圈、粉丝数未知"的人名号按 0 粉打到垫底。
NEUTRAL_POPULARITY = 45.0


def composite_score(sig: CandidateSignals) -> float:
    """0-100 综合分。各信号归一后加权;不活跃/机构号降权;像种子加成。"""
    popularity = popularity_score(sig.follower_count, sig.like_samples) if sig.popularity_known else NEUTRAL_POPULARITY
    # 命中方向权重直接当相关度(已是 0-100 量纲);不再 log 压到 ~20、让 45% 的相关度形同虚设。
    match = min(100.0, max(0.0, sig.matched_weight))

    base = 0.55 * popularity + 0.45 * match
    if sig.similarity_to_seed is not None:
        base = 0.7 * base + 0.3 * sig.similarity_to_seed  # 有种子:像不像种子占 3 成
    if not sig.active:
        base *= 0.85                  # 不活跃降权
    if not sig.is_personal:
        base *= 0.9                   # 机构/泛号轻降(学打法优先个人号)
    return round(min(100.0, max(0.0, base)), 1)


def rank(signals: list[CandidateSignals]) -> list[tuple[str, float]]:
    """返回 [(external_id, score)] 按分降序。"""
    scored = [(s.external_id, composite_score(s)) for s in signals]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
