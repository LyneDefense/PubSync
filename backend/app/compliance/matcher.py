"""一层 · 确定性匹配。词边界 + 白名单 + 上下文规则 + 置信度 → 候选命中。

这一层就是「降误报」的主战场:
- allow_words:命中词落在更长的允许词里则抑制(祛皱命中但「抗皱」允许;公安命中但「办公安排」)。
- allow_context:命中片段匹配口语语境则抑制(「还是最好」里的「最好」)。
- require_context:必须邻近特定语境才算(平台名 only if 邻近 去/搜/私域)。
- 同规则内子串吸收:「加微」⊂「加微信」只留长的。
纯函数、无 IO、可全离线测。
"""

from __future__ import annotations

import re

from app.compliance.types import Hit, Rule, RulePack

_PAD = 12  # 取片段(quote)左右各留几个字


def _normalize(text: str) -> str:
    """全角→半角 + ascii 转小写(逐字符,位置保持不变,方便回原文定位)。"""
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            code = 0x20
        elif 0xFF01 <= code <= 0xFF5E:
            code -= 0xFEE0
        out.append(chr(code))
    return "".join(out).lower()


def _window(text: str, start: int, end: int) -> str:
    s = max(0, start - _PAD)
    e = min(len(text), end + _PAD)
    return ("…" if s > 0 else "") + text[s:e] + ("…" if e < len(text) else "")


def _ascii_boundary_ok(text: str, start: int, end: int, word: str) -> bool:
    """纯 ascii 短词(如 vx / tb)要求两侧不是字母数字,避免误伤更大的英文串。"""
    if not word.isascii() or not word.isalnum():
        return True
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not (before.isalnum() or after.isalnum())


def _covered_by_allow_word(norm: str, start: int, end: int, matched: str, allow_words: tuple[str, ...]) -> bool:
    """命中片段 [start,end) 是否落在某个「更长的允许词」的出现范围内 → 抑制。"""
    for aw in allow_words:
        if matched not in aw or aw == matched:
            continue
        naw = _normalize(aw)
        i = norm.find(naw)
        while i >= 0:
            if i <= start and end <= i + len(naw):
                return True
            i = norm.find(naw, i + 1)
    return False


def _ctx_hit(window: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, window) for p in patterns)


def _rule_spans(norm: str, rule: Rule) -> list[tuple[int, int, str]]:
    """一条规则在一段文本里的所有命中 (start,end,matched),已做同规则内子串吸收(留最长)。"""
    spans: list[tuple[int, int, str]] = []
    for word in rule.words:
        w = _normalize(word)
        if not w:
            continue
        i = norm.find(w)
        while i >= 0:
            spans.append((i, i + len(w), word))
            i = norm.find(w, i + 1)
    for pat in rule.patterns:
        for m in re.finditer(pat, norm):
            spans.append((m.start(), m.end(), m.group(0)))
    # 子串吸收:长的优先,短的若被已保留的长命中覆盖则丢弃。
    spans.sort(key=lambda s: s[1] - s[0], reverse=True)
    kept: list[tuple[int, int, str]] = []
    for s, e, w in spans:
        if any(ks <= s and e <= ke for ks, ke, _ in kept):
            continue
        kept.append((s, e, w))
    return kept


def match_fields(fields: list[tuple[str, str]], packs: list[RulePack]) -> list[Hit]:
    """扫描 (字段名, 文本) 列表 → 候选命中。按 (pack,rule,词,文本序号) 去重。"""
    hits: list[Hit] = []
    seen: set[tuple[str, str, str, int]] = set()
    for note_index, (field_label, raw) in enumerate(fields):
        if not raw or not raw.strip():
            continue
        norm = _normalize(raw)
        for pack in packs:
            for rule in pack.rules:
                for start, end, matched in _rule_spans(norm, rule):
                    if not _ascii_boundary_ok(norm, start, end, _normalize(matched)):
                        continue
                    if _covered_by_allow_word(norm, start, end, _normalize(matched), rule.allow_words):
                        continue
                    window = _window(raw, start, end)
                    if rule.allow_context and _ctx_hit(_normalize(window), rule.allow_context):
                        continue
                    if rule.require_context and not _ctx_hit(_normalize(window), rule.require_context):
                        continue
                    key = (pack.id, rule.id, matched, note_index)
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(Hit(
                        pack_id=pack.id, rule_id=rule.id, category=rule.category,
                        matched=matched, quote=window, field=field_label,
                        severity=rule.severity, confidence=rule.confidence,
                        basis=rule.basis, hint=rule.hint, note_index=note_index, layer="rule",
                    ))
    return hits
