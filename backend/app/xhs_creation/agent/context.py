from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import BloggerProfile, BloggerSkill
from app.schemas import XhsPublishPackageCreate


@dataclass
class CreationContext:
    """一次创作合成的上下文，贯穿 guide/sensors/critic/benchmark。"""

    blogger: BloggerProfile
    skill: BloggerSkill
    payload: XhsPublishPackageCreate
    platform: str
    content_type: str
    # 对标博主的统计画像（来自该 Skill 对应蒸馏 run 的 report_json.stats），用于收敛后的对标对比；可为空。
    benchmark_stats: dict[str, Any] = field(default_factory=dict)
