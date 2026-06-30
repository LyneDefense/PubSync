"""合规共享引擎:把若干段文本扫成「结构化分级风险 + 合规分」。

两层:
- L1 词库/正则:快、准、便宜。命中内置词库(按品类启用红线),给分级 + 官方依据 + 改写建议。
- L2 语义(模型,可选):抓词库抓不到的——隐性广告、虚假人设、夸大功效、无资质荐荐/具体投资建议、品类越界。
  失败/超时直接跳过(只剩 L1),绝不阻断。

被三处复用:博主诊断(他人/自己)、蒸馏 skill 输出闸门。
"""

from __future__ import annotations

import logging
from typing import Any

from app.compliance import wordlists
from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

# 分级 → 扣分(后台可调;单类别封顶 40,避免一类把分清零)。
SEVERITY_PENALTY = {
    wordlists.SEVERITY_BAN: 40,
    wordlists.SEVERITY_THROTTLE: 15,
    wordlists.SEVERITY_NOTICE: 5,
}
_PER_CATEGORY_CAP = 40


def scan_l1(
    texts: list[str],
    platform: str,
    industry: str | None = None,
    extra_words: list[str] | None = None,
) -> list[dict[str, Any]]:
    """L1 词库扫描。返回命中 [{category, matched, severity, basis, suggestion, layer, quote}]。

    去重:同(类别,词)只记一次;子串命中被更长命中吸收(「加微」⊂「加微信」只留长的)。
    """
    blocklist = wordlists.build_blocklist(platform, industry)
    if extra_words:
        blocklist = {**blocklist, "自定义": [w for w in extra_words if w]}
    word_to_category = wordlists.flatten_blocklist(blocklist)

    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for text in texts:
        if not text:
            continue
        matched = [w for w in word_to_category if w and w in text]
        kept = [w for w in matched if not any(w != other and w in other for other in matched)]
        for word in kept:
            category = word_to_category[word]
            if (category, word) in seen:
                continue
            seen.add((category, word))
            hits.append({
                "category": category,
                "matched": word,
                "severity": wordlists.category_severity(category),
                "basis": wordlists.category_basis(category),
                "suggestion": wordlists.CATEGORY_HINTS.get(category, ""),
                "layer": "L1",
                "quote": _snippet(text, word),
            })
    return hits


def _snippet(text: str, word: str, pad: int = 12) -> str:
    i = text.find(word)
    if i < 0:
        return ""
    start = max(0, i - pad)
    end = min(len(text), i + len(word) + pad)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")


_L2_PROMPT = """你是小红书内容合规审核员。下面是某账号的若干条笔记文本(标题/正文)。请只挑出**词库难以命中、但确属违规**的语义级问题,每条给出原文片段、类别、严重度、依据、改法。

重点找(命中才报,没有就空数组,别硬凑):
- 隐性广告/虚假种草:测评/分享伪装硬广、隐藏商业关联
- 虚假人设:虚构财富/学历/收入/情感经历
- 夸大功效:把普通体验说成确定疗效/效果
- 无资质越界:无资质以医生/理财师/律师人设给具体诊断、治疗、投资建议{industry_line}
- 标题党/猎奇:夸张猎奇手段诱导点击

严重度三档:封号级 / 限流级 / 提示级。
只输出 JSON:{{"issues":[{{"category":"类别","quote":"原文片段","severity":"封号级|限流级|提示级","basis":"依据","suggestion":"怎么改"}}]}}

笔记文本:
{joined}
"""


def scan_l2(
    texts: list[str], settings: Settings, industry: str | None = None, *, timeout: int | None = None
) -> list[dict[str, Any]]:
    """L2 语义扫描(模型)。失败/超时/坏格式 → 返回空,绝不阻断。"""
    joined = "\n---\n".join(t.strip() for t in texts if t and t.strip())[:8000]
    if not joined:
        return []
    industry_line = f"(本账号品类:{industry},尤其注意该品类的资质红线)" if industry else ""
    prompt = _L2_PROMPT.format(industry_line=industry_line, joined=joined)
    try:
        data = create_json_response(settings, prompt, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - L2 失败只降级到 L1,不阻断
        logger.warning("合规 L2 语义扫描失败,仅用 L1:%s", exc)
        return []
    raw = data.get("issues") if isinstance(data, dict) else None
    out: list[dict[str, Any]] = []
    valid_sev = {wordlists.SEVERITY_BAN, wordlists.SEVERITY_THROTTLE, wordlists.SEVERITY_NOTICE}
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "语义风险").strip()
        severity = str(item.get("severity") or "").strip()
        if severity not in valid_sev:
            severity = wordlists.SEVERITY_THROTTLE
        out.append({
            "category": category,
            "matched": str(item.get("quote") or "").strip()[:40],
            "severity": severity,
            "basis": str(item.get("basis") or "").strip(),
            "suggestion": str(item.get("suggestion") or "").strip(),
            "layer": "L2",
            "quote": str(item.get("quote") or "").strip()[:80],
        })
    return out


def compliance_score(hits: list[dict[str, Any]]) -> int:
    """100 − 加权扣分(每类别封顶,整体下限 0)。越高越干净。"""
    by_cat: dict[str, int] = {}
    for h in hits:
        by_cat[h["category"]] = by_cat.get(h["category"], 0) + SEVERITY_PENALTY.get(h.get("severity"), 5)
    total = sum(min(p, _PER_CATEGORY_CAP) for p in by_cat.values())
    return max(0, 100 - total)


def verdict(hits: list[dict[str, Any]]) -> str:
    severities = {h.get("severity") for h in hits}
    if wordlists.SEVERITY_BAN in severities:
        return "高危(含封号级违规)"
    if wordlists.SEVERITY_THROTTLE in severities:
        return "有限流风险"
    if hits:
        return "轻微/边界"
    return "干净"


def compliance_scan(
    texts: list[str],
    platform: str,
    industry: str | None = None,
    *,
    settings: Settings | None = None,
    use_llm: bool = False,
    extra_words: list[str] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """完整扫描:L1(+可选 L2)→ 结构化结果。

    返回 {score, grade(verdict), hits[], by_severity{封号级:n,...}, has_ban}。
    """
    hits = scan_l1(texts, platform, industry, extra_words)
    if use_llm and settings is not None:
        hits = hits + scan_l2(texts, settings, industry, timeout=timeout)
    by_severity: dict[str, int] = {}
    for h in hits:
        by_severity[h["severity"]] = by_severity.get(h["severity"], 0) + 1
    return {
        "score": compliance_score(hits),
        "grade": verdict(hits),
        "hits": hits,
        "by_severity": by_severity,
        "has_ban": wordlists.SEVERITY_BAN in {h.get("severity") for h in hits},
    }
