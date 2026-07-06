"""对标分析·「我 vs TA」差距(#22 P2):

- B 事实差(规则、便宜、总有):体量 / 更新频率 / 互动效率。
- A 创作打法 diff(双方都蒸过创作画像才有,一次 LLM):选题/标题/开头/结构/语言DNA/CTA。
纯计算 + 单次 LLM,失败降级不挡诊断。
"""

from __future__ import annotations

import logging
from datetime import timedelta
from statistics import median
from typing import Any

from app.config import Settings
from app.models import BloggerPost, BloggerProfile
from app.models.common import utc_now
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)


def _fmt_count(v: float) -> str:
    n = int(round(v))
    if n >= 10000:
        return f"{round(n / 10000, 1):g}w"  # 5.0→5、1.2→1.2、12.3→12.3
    return str(n)


def _per_week(posts: list[BloggerPost], days: int = 90) -> float:
    """近 days 天发文的篇/周;无发布时间的忽略。"""
    cutoff = utc_now() - timedelta(days=days)
    recent = sum(1 for p in posts if p.published_at and p.published_at >= cutoff)
    return round(recent / (days / 7), 1)


def _median_eng(posts: list[BloggerPost]) -> float:
    vals = [(p.like_count or 0) + (p.favorite_count or 0) for p in posts]
    return float(median(vals)) if vals else 0.0


def _cmp_text(me: float, ta: float) -> str:
    """一句话差距(赞越高越好):领先/落后 + 倍数。"""
    if me <= 0 and ta <= 0:
        return "两边都很低"
    if me == ta:
        return "基本持平"
    hi, lo = max(me, ta), min(me, ta)
    ratio = hi / lo if lo > 0 else 0
    scale = f"约 {ratio:.1f} 倍" if (lo > 0 and ratio >= 1.5) else "略高"
    return ("你领先 " if me > ta else "你落后 ") + scale


def _fact_diff(mine: BloggerProfile, ta: BloggerProfile, mine_pool, ta_pool) -> list[dict[str, Any]]:
    def row(aspect: str, me: float, tav: float, fmt) -> dict[str, Any]:
        return {"aspect": aspect, "me": fmt(me), "ta": fmt(tav), "gap": _cmp_text(me, tav)}

    return [
        row("体量·粉丝", mine.follower_count or 0, ta.follower_count or 0, _fmt_count),
        row("更新·篇/周", _per_week(mine_pool), _per_week(ta_pool), lambda v: f"{v:.1f}"),
        row("互动·中位赞藏", _median_eng(mine_pool), _median_eng(ta_pool), _fmt_count),
    ]


_PLAYBOOK_PROMPT = """对比两个博主的创作打法,找出「我」相比「对标博主」的差距。{intent_line}

【对标博主(要学的打法)】
{ta}

【我的账号(现状打法)】
{me}

只挑差距明显的 3–6 条,输出 JSON(不要 Markdown、不要解释):
{{"items":[{{"aspect":"选题/标题/开头/结构/语言DNA/CTA 之一","ta":"TA 怎么干(≤20字)","me":"我怎么干(≤20字)","gap":"差在哪+怎么补(一句≤30字)"}}],"summary":"一句话总差距(≤40字)"}}"""


def _playbook_diff(settings: Settings, me_md: str, ta_md: str, intent: str, timeout: int) -> dict[str, Any] | None:
    intent_line = f"用户想学的方向:{intent.strip()}。" if intent.strip() else ""
    prompt = _PLAYBOOK_PROMPT.format(intent_line=intent_line, ta=ta_md[:6000], me=me_md[:6000])
    try:
        data = create_json_response(settings, prompt, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - diff 是增强,失败不挡诊断
        logger.warning("画像 diff 失败,跳过:%s", exc)
        return None
    if not isinstance(data, dict):
        return None
    items = [
        {"aspect": str(it.get("aspect") or ""), "ta": str(it.get("ta") or ""),
         "me": str(it.get("me") or ""), "gap": str(it.get("gap") or "")}
        for it in (data.get("items") or []) if isinstance(it, dict)
    ][:6]
    return {"items": items, "summary": str(data.get("summary") or "")} if items else None


def build_gap(
    settings: Settings, mine: BloggerProfile, ta: BloggerProfile,
    mine_pool: list[BloggerPost], ta_pool: list[BloggerPost],
    mine_skill_md: str, ta_skill_md: str, intent: str, timeout: int,
) -> dict[str, Any]:
    """我 vs TA:B 事实差(总有)+ A 打法 diff(双方都蒸过才有,否则给提示)。"""
    both_distilled = bool(mine_skill_md and ta_skill_md)
    return {
        "mine_name": mine.display_name or "我的账号",
        "ta_name": ta.display_name or "对标博主",
        "facts": _fact_diff(mine, ta, mine_pool, ta_pool),
        "playbook": _playbook_diff(settings, mine_skill_md, ta_skill_md, intent, timeout) if both_distilled else None,
        "note": None if both_distilled else "给「我的账号」建档并蒸馏创作画像后,才能逐条对拍创作打法。",
    }
