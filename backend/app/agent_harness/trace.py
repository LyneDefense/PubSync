from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AttemptRecord:
    """单次模型尝试的可观测记录（harness engineering 的 observability）。"""

    attempt: int
    model: str | None
    elapsed_seconds: float
    score: int | None
    passed: bool
    issues: list[str] = field(default_factory=list)
    # 喂给「本次」尝试的纠错反馈（首次为空，修订时来自上一次的 sensor）。
    revised_with: str = ""


@dataclass
class HarnessTrace:
    """一次合成（生成→校验→修订）的完整轨迹。"""

    task: str
    attempts: list[AttemptRecord] = field(default_factory=list)
    final_attempt: int = 0
    final_score: int | None = None
    final_passed: bool = False
    revisions: int = 0  # 首次之外的修订次数

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "revisions": self.revisions,
            "final_attempt": self.final_attempt,
            "final_score": self.final_score,
            "final_passed": self.final_passed,
            "attempts": [record.__dict__ for record in self.attempts],
        }
