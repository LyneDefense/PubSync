"""对标分析·意图引导:看博主在做什么 → 判断用户填的意图够不够具体 → 不够就出几个多选题帮他明确。

一次便宜的小模型调用,顺带判「清晰度」:
- 意图已具体(说清了想学这个号的哪些方面/什么目标)→ clear=true,不出题,直接能诊断。
- 空 / 太泛("学他涨粉")→ clear=false,出 1-3 个题,每题 3-4 个贴这个号实际内容的选项,让用户多选 + 可填「其他」。
失败 / 坏格式 / 无素材 → 按「有没有填」兜底(填了放行、没填给一组通用题),绝不阻断诊断。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

# 判不了时的通用兜底题(没素材 / 模型失败 且用户没填意图时用)。
# benchmark:外向「想跟 TA 学什么」;self:内向「想让诊断为我达成什么」(目标 / 痛点 / 阶段)。
_GENERIC_QUESTIONS = [
    {"q": "你最想跟 TA 学哪方面?", "options": ["选题 / 内容方向", "标题与开头钩子", "内容形态与节奏", "变现 / 引流路径"],
     "multi": True, "allow_other": True},
    {"q": "你的目标是?", "options": ["涨粉做 IP", "带货变现", "引流到私域 / 转化"], "multi": False, "allow_other": True},
]
_GENERIC_SELF_QUESTIONS = [
    {"q": "这个号你最想先达成什么?", "options": ["涨粉做大", "提高互动(赞藏评)", "提升转化(获客 / 带货 / 引流)", "立人设 · 明确定位"],
     "multi": True, "allow_other": True},
    {"q": "现在最大的卡点是?", "options": ["不知道发什么(选题)", "有曝光没点击", "有点击没互动", "有互动没转化", "更新难坚持"],
     "multi": True, "allow_other": True},
    {"q": "账号目前处于哪个阶段?", "options": ["刚起号 · 摸索期", "卡在某个粉丝量", "想突破瓶颈 / 转型"], "multi": False, "allow_other": False},
]

_PROMPT = """你在帮一个想做对标的博主明确「他想跟某个账号学什么」。

被参考账号近期在做的内容(标题 + 标签 + 赛道):
{content}

用户当前填的对标意图(可能为空、可能很泛):{intent}

任务:
1. 判断用户填的意图**是否已经具体到可以直接拿来诊断**——要明确说了想学这个号的哪些方面 / 想达到什么目标才算具体;空的、或"学他涨粉""想对标他"这种泛话都不算。
2. 已经够具体 → clear=true,questions 给空数组。
3. 不够 → clear=false,基于这个账号**真实在做的内容**,出 1-3 个帮他明确意图的问题。每个问题给 3-4 个选项,选项要贴这个号的实际内容(从标题/标签提炼成用户能"学"的点)。
   每题标注 multi(是否可多选)与 allow_other(是否允许"其他,自己填"):可并存的方面(如想学的多个点)用 multi=true;互斥的单一目标用 multi=false。

只输出 JSON:
{{"clear": true/false,
  "questions": [{{"q": "你最想跟 TA 学哪方面?", "options": ["选题套路", "涨粉钩子写法", "不露脸口播形式", "引流变现路径"], "multi": true, "allow_other": true}}]}}"""

# 诊断「我自己的号」:意图是内向的——目标 / 痛点 / 阶段,而不是「想学别人什么」。
_SELF_PROMPT = """你在帮一个博主明确「他想让这次『账号诊断』为他解决什么」——注意诊断的是他**自己的号**,不是对标别人。

他自己账号近期在做的内容(标题 + 标签 + 赛道):
{content}

他当前填的诉求(可能为空、可能很泛):{intent}

任务:
1. 判断他填的诉求**是否已经具体到能据此定制诊断**——说清了经营目标(涨粉 / 互动 / 转化 / 立人设…)或具体卡点才算;空的、或"想做好""涨粉"这种泛话都不算。
2. 已经够具体 → clear=true,questions 给空数组。
3. 不够 → clear=false,出 1-3 个帮他说清**目标 / 痛点 / 阶段**的问题,每题 3-4 个选项,选项贴他这个号的实际情况。
   每题标注 multi(是否可多选)与 allow_other(是否允许"其他,自己填"):目标 / 痛点可并存用 multi=true;阶段这类互斥单选用 multi=false。

只输出 JSON:
{{"clear": true/false,
  "questions": [{{"q": "这个号你最想先达成什么?", "options": ["涨粉做大", "提高互动", "提升转化(获客 / 带货)", "立人设 · 定位"], "multi": true, "allow_other": true}}]}}"""


def suggest_intent(
    settings: Settings,
    *,
    titles: list[str],
    tags: list[str],
    niche: str = "",
    intent: str = "",
    purpose: str = "benchmark",
    timeout: int | None = None,
) -> dict[str, Any]:
    """返回 {"clear": bool, "questions": [{"q": str, "options": [str]}]}。

    purpose='benchmark'(默认):对标别人,意图=想学什么;'self':诊断自己,意图=目标/痛点/阶段。
    """
    intent = (intent or "").strip()
    is_self = purpose == "self"
    generic = _GENERIC_SELF_QUESTIONS if is_self else _GENERIC_QUESTIONS
    prompt_tpl = _SELF_PROMPT if is_self else _PROMPT
    content = _build_content(titles, tags, niche)
    if not content:  # 没素材判不了 → 有填就放行,没填给通用题。
        return {"clear": bool(intent), "questions": [] if intent else generic}
    try:
        data = create_json_response(
            settings, prompt_tpl.format(content=content, intent=intent or "(空)"), timeout=timeout
        )
    except Exception as exc:  # noqa: BLE001 - 引导失败不该挡诊断
        logger.warning("意图引导失败,兜底:%s", exc)
        return {"clear": bool(intent), "questions": [] if intent else generic}
    if not isinstance(data, dict):
        return {"clear": bool(intent), "questions": [] if intent else generic}
    if bool(data.get("clear")):
        return {"clear": True, "questions": []}
    questions = _clean_questions(data.get("questions"))
    return {"clear": False, "questions": questions or generic}


def _build_content(titles: list[str], tags: list[str], niche: str) -> str:
    parts: list[str] = []
    if niche and niche.strip():
        parts.append(f"赛道:{niche.strip()}")
    clean_tags = [t.strip() for t in tags if t and t.strip()]
    if clean_tags:
        parts.append("标签:" + "、".join(clean_tags)[:300])
    clean_titles = [t.strip() for t in titles if t and t.strip()][:30]
    if clean_titles:
        parts.append("近期标题:\n" + "\n".join(f"- {t}" for t in clean_titles)[:2500])
    return "\n".join(parts).strip()


def _clean_questions(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        q = str(item.get("q") or "").strip()
        options = [str(o).strip() for o in (item.get("options") or []) if str(o).strip()]
        if q and len(options) >= 2:
            out.append({
                "q": q,
                "options": options[:4],
                "multi": bool(item.get("multi", True)),  # 缺省=可多选(更宽松)
                "allow_other": bool(item.get("allow_other", True)),
            })
    return out[:3]
