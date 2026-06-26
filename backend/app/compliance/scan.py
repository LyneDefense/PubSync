"""扫描创作产出里的限流/违禁词命中。纯函数、无 IO。"""

from __future__ import annotations

from typing import Any

from app.compliance.wordlists import build_blocklist, category_severity, flatten_blocklist


def _iter_fields(result: dict[str, Any]) -> list[tuple[str, str]]:
    """把创作产出摊平成 (字段中文名, 文本) 列表,覆盖所有面向读者的文字。"""
    fields: list[tuple[str, str]] = []
    fields.append(("标题", str(result.get("title") or "")))
    fields.append(("正文", str(result.get("body_text") or "")))
    fields.append(("封面文案", str(result.get("cover_text") or "")))
    for tag in result.get("hashtags") or []:
        fields.append(("标签", str(tag)))
    script = result.get("script") or {}
    if isinstance(script, dict):
        for seg in script.get("segments") or []:
            if isinstance(seg, dict):
                for key, label in (("voiceover", "口播"), ("subtitle", "字幕"), ("scene", "画面")):
                    if seg.get(key):
                        fields.append((label, str(seg.get(key))))
        for note in script.get("shooting_notes") or []:
            fields.append(("拍摄建议", str(note)))
    return fields


def scan_creation_output(
    result: dict[str, Any],
    platform: str,
    extra_words: list[str] | None = None,
) -> list[dict[str, str]]:
    """扫描创作产出,返回命中列表 [{word, field, category}](去重:同词同字段只记一次)。"""
    blocklist = build_blocklist(platform)
    if extra_words:
        blocklist = {**blocklist, "自定义": [w for w in extra_words if w]}
    word_to_category = flatten_blocklist(blocklist)

    hits: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for field_label, text in _iter_fields(result):
        if not text:
            continue
        matched = [w for w in word_to_category if w and w in text]
        # 同一字段里,若某命中词是另一命中词的子串(如「加微」⊂「加微信」),只保留更长的那个。
        kept = [w for w in matched if not any(w != other and w in other for other in matched)]
        for word in kept:
            if (word, field_label) not in seen:
                seen.add((word, field_label))
                category = word_to_category[word]
                hits.append({"word": word, "field": field_label, "category": category,
                             "severity": category_severity(category)})
    return hits
