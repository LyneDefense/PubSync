from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.synthesis.budget import SynthesisBudget
from app.synthesis.guide import TaskGuide, with_feedback
from app.synthesis.sensors import Sensor, evaluate_sensors
from app.synthesis.trace import AttemptRecord, SynthesisTrace
from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

# 推理型评审：读已生成结果，产出面向模型的纠错反馈（贵，仅在需要修订前调用）。
Critic = Callable[[dict[str, Any], Any], str]


def run_synthesis(
    settings: Settings,
    guide: TaskGuide,
    context: Any,
    sensors: list[Sensor],
    budget: SynthesisBudget,
    model: str | None = None,
    critic: Critic | None = None,
) -> tuple[dict[str, Any], SynthesisTrace]:
    """生成 → 校验 → 修订 的有界循环（生成-校验-修订核心）。

    每轮：用 guide 构造提示词 → 调模型 → normalize → 跑计算型 sensors。
    达标（全部通过且分数≥min_score）即停；否则用 sensors（必要时叠加 critic）的纠错反馈
    重新提示，直到达标或用尽 budget.max_attempts。用尽则返回分数最高的那一版。
    """
    trace = SynthesisTrace(task=guide.name)
    feedback = ""
    best_score: int | None = None
    best_result: dict[str, Any] | None = None

    for attempt in range(1, max(1, budget.max_attempts) + 1):
        started = time.perf_counter()
        prompt = with_feedback(guide.build_prompt(context), feedback)
        data = create_json_response(settings, prompt, model=model)
        if guide.normalize:
            data = guide.normalize(data, context)
        elapsed = round(time.perf_counter() - started, 2)

        verdict = evaluate_sensors(sensors, data, context)
        trace.attempts.append(
            AttemptRecord(
                attempt=attempt,
                model=model,
                elapsed_seconds=elapsed,
                score=verdict.score,
                passed=verdict.passed,
                issues=verdict.issues,
                revised_with=feedback,
            )
        )
        if best_result is None or (verdict.score is not None and (best_score is None or verdict.score > best_score)):
            best_score, best_result = verdict.score, data

        meets_score = verdict.score is None or verdict.score >= budget.min_score
        if verdict.passed and meets_score:
            return _finish(trace, attempt, verdict.score, True, data)

        if attempt >= budget.max_attempts:
            break

        # 准备下一轮的纠错反馈：计算型反馈 +（可选）推理型评审，仅在确实要修订时才付费调用 critic。
        feedback = verdict.corrective_feedback
        if critic is not None:
            try:
                critic_feedback = critic(data, context)
            except Exception as exc:  # critic 失败不应中断主流程
                logger.warning("合成评审失败：task=%s attempt=%s err=%s", guide.name, attempt, exc)
                critic_feedback = ""
            if critic_feedback.strip():
                feedback = f"{feedback}\n【深度评审】{critic_feedback.strip()}" if feedback else critic_feedback.strip()
        logger.info("合成修订：task=%s attempt=%s score=%s issues=%s", guide.name, attempt, verdict.score, len(verdict.issues))

    chosen = best_result if best_result is not None else data
    return _finish(trace, len(trace.attempts), best_score, False, chosen)


def _finish(trace: SynthesisTrace, final_attempt: int, score: int | None, passed: bool, data: dict[str, Any]) -> tuple[dict[str, Any], SynthesisTrace]:
    trace.final_attempt = final_attempt
    trace.final_score = score
    trace.final_passed = passed
    trace.revisions = max(0, len(trace.attempts) - 1)
    return data, trace
