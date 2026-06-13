from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class SensorResult:
    """传感器（feedback control）的检查结果。

    passed：本传感器是否通过（阻断型传感器不通过会强制修订）。
    score：可选 0-100 质量分（评分型传感器提供）。
    issues：人类可读的问题列表。
    corrective_feedback：给模型看的纠错指令（Fowler 强调：反馈要面向 LLM 消费）。
    """

    passed: bool
    score: int | None = None
    issues: list[str] = field(default_factory=list)
    corrective_feedback: str = ""


@runtime_checkable
class Sensor(Protocol):
    name: str

    def check(self, result: dict[str, Any], context: Any) -> SensorResult: ...


@dataclass
class SensorVerdict:
    """对一组计算型传感器结果的聚合判定。"""

    passed: bool
    score: int | None
    issues: list[str]
    corrective_feedback: str


def evaluate_sensors(sensors: list[Sensor], result: dict[str, Any], context: Any) -> SensorVerdict:
    """按顺序运行计算型传感器并聚合。

    - passed = 所有传感器都通过。
    - score = 取最后一个提供分数的传感器（约定：评分型传感器排在后面）。
    - issues / corrective_feedback 合并所有有反馈的传感器（含通过但有改进项的）。
    """
    all_passed = True
    score: int | None = None
    issues: list[str] = []
    feedback_blocks: list[str] = []
    for sensor in sensors:
        outcome = sensor.check(result, context)
        if not outcome.passed:
            all_passed = False
        if outcome.score is not None:
            score = outcome.score
        issues.extend(outcome.issues)
        if outcome.corrective_feedback.strip():
            feedback_blocks.append(f"【{sensor.name}】{outcome.corrective_feedback.strip()}")
    return SensorVerdict(
        passed=all_passed,
        score=score,
        issues=issues,
        corrective_feedback="\n".join(feedback_blocks),
    )
