from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.services.ai_service import create_json_response
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.platforms import PLATFORM_SPECS

logger = logging.getLogger(__name__)


def build_benchmark_comparison(settings: Settings, generated: dict[str, Any], ctx: CreationContext, model: str | None) -> dict[str, Any]:
    """收敛后的一次性「对标对比」:把生成稿与对标博主的方法论/数据画像比对,产出结构化结论。

    失败不抛错(对比只是加分项),返回空骨架。
    """
    platform_name = PLATFORM_SPECS[ctx.platform].name
    stats_brief = _stats_brief(ctx.benchmark_stats)
    draft_brief = {
        "title": generated.get("title"),
        "body_text": str(generated.get("body_text") or "")[:1500],
        "hashtags": generated.get("hashtags"),
    }
    prompt = f"""你是{platform_name}创作教练。请把“用户这篇草稿”和“对标博主的方法论与数据画像”做一次对比,
评估它有多贴近对标博主的爆款套路,并指出还差哪些。用通俗中文,不要术语、不要代码。

只输出 JSON:
{{
  "title_fit": "标题贴合度的一句话点评",
  "language_fit": "语言/口吻贴合度的一句话点评",
  "formula_fit": "与对标博主爆款套路吻合度的一句话点评",
  "gaps": ["还差哪些(可执行,1-4 条)"],
  "summary": "一句话总结这篇离对标博主还有多远、强在哪"
}}

对标博主方法论摘要:{ctx.skill.skill_markdown[:3500]}
对标博主数据画像:{json.dumps(stats_brief, ensure_ascii=False, default=str)[:2500]}
用户草稿:{json.dumps(draft_brief, ensure_ascii=False, default=str)[:2500]}
"""
    try:
        data = create_json_response(settings, prompt, model=model)
    except Exception as exc:  # 对比失败不影响主产物
        logger.warning("对标对比生成失败:%s", exc)
        return {}
    return {
        "title_fit": str(data.get("title_fit") or "").strip(),
        "language_fit": str(data.get("language_fit") or "").strip(),
        "formula_fit": str(data.get("formula_fit") or "").strip(),
        "gaps": [str(x).strip() for x in (data.get("gaps") or []) if str(x).strip()][:4],
        "summary": str(data.get("summary") or "").strip(),
    }


def _stats_brief(stats: dict[str, Any]) -> dict[str, Any]:
    """从蒸馏 stats 里挑几项最有对标价值的画像,避免把超大 stats 全塞进提示词。"""
    if not isinstance(stats, dict):
        return {}
    brief: dict[str, Any] = {}
    for key in ("title_patterns", "cta_patterns", "opening_patterns"):
        value = stats.get(key)
        if isinstance(value, dict):
            brief[key] = {k: v.get("pct") if isinstance(v, dict) else v for k, v in list(value.items())[:6]}
    for key in ("average_like", "average_favorite", "average_comment"):
        if stats.get(key) is not None:
            brief[key] = stats.get(key)
    hashtags = stats.get("frequent_hashtags")
    if isinstance(hashtags, list):
        brief["frequent_hashtags"] = [h.get("tag") if isinstance(h, dict) else h for h in hashtags[:10]]
    return brief
