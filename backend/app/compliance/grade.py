"""三层 · 归并 / 分级 / 算分。候选命中 → ScanResult。

两个操作点(mode):
- diagnose(诊断):精确优先。只有 certain + 封号/限流 才算「违规」;weak / 提示级 归「优化提示」。
- creation(创作闸门):召回优先。封号/限流一律拦(自己草稿可改);提示级不拦。

归并:同 (pack,rule) 的多条命中并成一条,带命中词 + 覆盖占比(命中 X/Y 篇)+ 样例。
算分:只由「违规」项决定,每类封顶,提示级不扣分。
"""

from __future__ import annotations

from app.compliance.types import Confidence, Hit, ScanResult, Severity

SEVERITY_PENALTY = {Severity.BAN.value: 40, Severity.THROTTLE.value: 15, Severity.NOTICE.value: 5}
_PER_CATEGORY_CAP = 40
_ACTIONABLE = (Severity.BAN.value, Severity.THROTTLE.value)


def grade(hits: list[Hit], total_notes: int, verticals: list[str], *, mode: str = "diagnose") -> ScanResult:
    groups: dict[tuple[str, str], list[Hit]] = {}
    for h in hits:
        groups.setdefault((h.pack_id, h.rule_id), []).append(h)

    violations: list[dict] = []
    advisories: list[dict] = []
    flat: list[dict] = []
    flat_seen: set[tuple[str, str, str, str]] = set()

    for (pid, rid), hs in groups.items():
        rep = hs[0]
        matched_words = list(dict.fromkeys(h.matched for h in hs))
        note_idxs = {h.note_index for h in hs}
        samples = list(dict.fromkeys(h.quote for h in hs if h.quote))[:2]
        group = {
            "category": rep.category,
            "severity": rep.severity.value,
            "basis": rep.basis,
            "hint": rep.hint,
            "matched": matched_words,
            "coverage": {"hit_notes": len(note_idxs), "total_notes": total_notes},
            "samples": samples,
            "note_idxs": sorted(note_idxs),  # 命中所在笔记序号;调用方可映射成标题(如档案合规)
        }
        # 扁平命中(创作闸门 + 兼容旧前端 compliance.hits):按 (rule,词,字段) 去重
        for h in hs:
            key = (pid, rid, h.matched, h.field)
            if key in flat_seen:
                continue
            flat_seen.add(key)
            flat.append({
                "word": h.matched, "field": h.field, "category": h.category,
                "severity": h.severity.value, "hint": h.hint, "basis": h.basis, "quote": h.quote,
            })

        if mode == "diagnose":
            is_violation = rep.confidence == Confidence.CERTAIN and rep.severity.value in _ACTIONABLE
        else:  # creation
            is_violation = rep.severity.value in _ACTIONABLE
        (violations if is_violation else advisories).append(group)

    # 算分:只由违规项决定,按类别封顶
    by_cat: dict[str, int] = {}
    for g in violations:
        by_cat[g["category"]] = by_cat.get(g["category"], 0) + SEVERITY_PENALTY.get(g["severity"], 5)
    score = max(0, 100 - sum(min(p, _PER_CATEGORY_CAP) for p in by_cat.values()))

    by_severity: dict[str, int] = {}
    for g in violations:
        by_severity[g["severity"]] = by_severity.get(g["severity"], 0) + 1
    has_ban = any(g["severity"] == Severity.BAN.value for g in violations)
    has_throttle = any(g["severity"] == Severity.THROTTLE.value for g in violations)
    grade_text = ("高危(含封号级违规)" if has_ban
                  else "有限流风险" if has_throttle
                  else "轻微/边界" if advisories
                  else "干净")

    # 违规排前(封号→限流),优化提示按类稳定排序
    violations.sort(key=lambda g: 0 if g["severity"] == Severity.BAN.value else 1)
    return ScanResult(
        score=score, grade=grade_text, has_ban=has_ban, verticals=list(verticals),
        violations=violations, advisories=advisories, flat_hits=flat, by_severity=by_severity,
    )
