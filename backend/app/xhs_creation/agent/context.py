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
    # 蒸馏结构化结果（report_json.distillation），用于装配「创作套件」；老 skill 可能为空,那时回落 skill_markdown。
    distillation: dict[str, Any] = field(default_factory=dict)
    # 租户自定义的额外限流词（来自 AppSetting，可为空）；与内置词库合并后参与合规检查。
    extra_block_words: list[str] = field(default_factory=list)
    # 是否启用限流词规避（提示词段 + 阻断 sensor）；由 settings.creation_compliance_enabled 决定。
    compliance_enabled: bool = True
