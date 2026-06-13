from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditContext:
    """一次账号体检/对标的上下文:用户自有内容 vs 对标博主的方法论与数据画像。"""

    platform: str
    platform_name: str
    benchmark_name: str
    skill_markdown: str
    my_content: str
    benchmark_stats: dict[str, Any] = field(default_factory=dict)
