"""Skill 优化(训练)模块。

M1 阶段先落地训练信号内核:风格指纹 + StyleDist 相似度 + 归属判别 + 锚点/gap_closed,
供 SkillOpt 的 rollout 当奖励(soft)与门控用。详见 docs/Skill优化_方案设计.md。
"""

from app.skill_optimization.style_metrics import (
    StyleProfile,
    attribution,
    build_profile,
    extract_features,
    gap_closed,
    style_similarity,
)

__all__ = [
    "StyleProfile",
    "attribution",
    "build_profile",
    "extract_features",
    "gap_closed",
    "style_similarity",
]
