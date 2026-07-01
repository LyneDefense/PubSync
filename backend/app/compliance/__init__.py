"""合规检测 · 统一公共组件。

合规是底层能力,被多处复用(博主诊断 / 自诊 / 创作闸门 / 创作提示注入)。
**所有调用方只走这里暴露的三个函数**,不要直接碰内部层:
- scan_account(...)  → 诊断:扫一个账号的多篇笔记,精确优先,返回 ScanResult(富报告)。
- scan_creation(...) → 创作闸门:扫一份创作产出,召回优先,返回 ScanResult(可取 .creation_dict())。
- prompt_guidance(...) → 给创作提示词注入「限流词规避」说明。

架构(两轴 × 三层)见 docs/合规检测_架构重构方案.md。P1 只落一层(matcher)+三层(grade);
二层 LLM 裁判(adjudicator)在 P2 接入,scan_* 已预留 settings/use_llm 形参,届时零改调用方。
"""

from __future__ import annotations

from typing import Any

from app.compliance.grade import grade
from app.compliance.matcher import match_fields
from app.compliance.registry import activate_packs, make_custom_pack
from app.compliance.types import (
    Confidence,
    Hit,
    Rule,
    RulePack,
    ScanResult,
    Severity,
    vertical_label,
)
from app.compliance.vertical import detect_verticals


def _resolve_verticals(niche: str, industry: str, tags: list[str] | None, titles: list[str] | None) -> list[str]:
    strong = " ".join([niche or "", industry or ""])
    return detect_verticals(strong, tags or [], titles or [])


def scan_account(
    texts: list[str],
    platform: str,
    *,
    niche: str = "",
    industry: str = "",
    tags: list[str] | None = None,
    titles: list[str] | None = None,
    extra_words: list[str] | None = None,
    settings: Any = None,   # P2 LLM 裁判用
    use_llm: bool = False,  # P2 LLM 裁判用
    timeout: int | None = None,
) -> ScanResult:
    """诊断一个账号:按赛道激活规则包 → 一层匹配 →(P2 二层裁判)→ 三层归并分级。精确优先。"""
    verticals = _resolve_verticals(niche, industry, tags, titles)
    packs = activate_packs(platform, verticals)
    custom = make_custom_pack(extra_words)
    if custom:
        packs = packs + [custom]
    fields = [("笔记", t) for t in texts]
    hits = match_fields(fields, packs)
    # P2: hits = adjudicate(hits, ..., settings, use_llm, timeout)
    total = len([t for t in texts if t and t.strip()])
    return grade(hits, total_notes=total, verticals=verticals, mode="diagnose")


def _creation_fields(result: dict[str, Any]) -> list[tuple[str, str]]:
    """把创作产出摊平成 (字段名, 文本),覆盖所有面向读者的文字。"""
    fields: list[tuple[str, str]] = [
        ("标题", str(result.get("title") or "")),
        ("正文", str(result.get("body_text") or "")),
        ("封面文案", str(result.get("cover_text") or "")),
    ]
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
    for plan in result.get("image_plan") or []:
        if isinstance(plan, dict) and plan.get("caption"):
            fields.append(("配图文案", str(plan.get("caption"))))
    return fields


def scan_creation(
    result: dict[str, Any],
    platform: str,
    *,
    niche: str = "",
    industry: str = "",
    extra_words: list[str] | None = None,
    settings: Any = None,
    use_llm: bool = False,
) -> ScanResult:
    """创作闸门:扫一份创作产出。召回优先(封号/限流一律拦),提示级不拦。"""
    verticals = _resolve_verticals(niche, industry, None, None)
    packs = activate_packs(platform, verticals)
    custom = make_custom_pack(extra_words)
    if custom:
        packs = packs + [custom]
    hits = match_fields(_creation_fields(result), packs)
    return grade(hits, total_notes=1, verticals=verticals, mode="creation")


def prompt_guidance(platform: str, verticals: list[str] | None = None, examples_per_rule: int = 4) -> str:
    """给创作提示词注入的「限流词规避」精简说明:各规则几个例词 + 改法(只列会限流/封号的)。"""
    packs = activate_packs(platform, verticals or [])
    lines: list[str] = []
    for pack in packs:
        for rule in pack.rules:
            if rule.severity == Severity.NOTICE or not rule.words:
                continue
            sample = "、".join(rule.words[:examples_per_rule])
            lines.append(f"- {rule.category}(如 {sample} 等):{rule.hint}")
    return "\n".join(lines)


__all__ = [
    "scan_account",
    "scan_creation",
    "prompt_guidance",
    "detect_verticals",
    "ScanResult",
    "Severity",
    "Confidence",
    "Rule",
    "RulePack",
    "Hit",
    "vertical_label",
]
