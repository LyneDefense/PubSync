from __future__ import annotations

from typing import Any

from app.account_audit.agent.context import AuditContext
from app.synthesis import SensorResult


class AuditSchemaSensor:
    """阻断型:结论必须有最基本的结构,否则强制修订。kind 不同要求不同。"""

    name = "结构完整性"

    def check(self, result: dict[str, Any], ctx: AuditContext) -> SensorResult:
        missing: list[str] = []
        if ctx.kind == "self":
            if not (result.get("strengths") or result.get("gaps")):
                missing.append("缺少优势/短板,至少给出账号已经做对的或明显短板")
        else:
            if len(result.get("dimensions") or []) < 3:
                missing.append("逐维度对比太少,至少给出 3 个维度(选题/标题/结构/表达/互动)的对比")
        if not str(result.get("conclusion") or "").strip():
            missing.append("缺少总体结论,请补一段话说明最该先补哪里")
        if missing:
            return SensorResult(passed=False, issues=missing, corrective_feedback="；".join(missing))
        return SensorResult(passed=True)


class AuditQualitySensor:
    """评分型:用确定性规则评完整度与可执行性。"""

    name = "质量评分"

    def check(self, result: dict[str, Any], ctx: AuditContext) -> SensorResult:
        quality = evaluate_audit_quality(result, kind=ctx.kind)
        feedback = "；".join(quality["issues"]) if quality["issues"] else ""
        return SensorResult(passed=True, score=quality["score"], issues=quality["issues"], corrective_feedback=feedback)


def evaluate_audit_quality(result: dict[str, Any], kind: str = "benchmark") -> dict[str, Any]:
    issues: list[str] = []
    score = 100

    def deduct(amount: int, ok: bool, detail: str) -> None:
        nonlocal score
        if not ok:
            score -= amount
            issues.append(detail)

    if kind == "self":
        deduct(25, bool(result.get("strengths")), "没有指出账号已经做对的地方")
        deduct(25, len(result.get("gaps") or []) >= 1, "没有点出明显短板")
        deduct(30, len(result.get("actions") or []) >= 2, "可立即执行的增长动作太少(建议 ≥2 条)")
        deduct(10, len(str(result.get("conclusion") or "")) >= 20, "总体结论太短,不够具体")
    else:
        dims = result.get("dimensions") or []
        deduct(25, len(dims) >= 5, f"逐维度对比 {len(dims)} 条,建议覆盖 5 个维度")
        complete_dims = sum(1 for d in dims if d.get("mine") and d.get("benchmark") and d.get("gap"))
        deduct(20, not dims or complete_dims >= max(3, len(dims) - 1), "部分维度缺少「对标做法/你的做法/差距」三要素")
        deduct(10, bool(result.get("strengths")), "没有指出用户已经做对的地方")
        deduct(15, len(result.get("gaps") or []) >= 1, "没有点出明显短板")
        deduct(20, len(result.get("actions") or []) >= 2, "可立即执行的改进动作太少(建议 ≥2 条)")
        deduct(10, len(str(result.get("conclusion") or "")) >= 20, "总体结论太短,不够具体")

    score = max(0, min(100, score))
    grade = "优" if score >= 85 else ("良" if score >= 70 else "待改进")
    return {"score": score, "grade": grade, "issues": issues}
