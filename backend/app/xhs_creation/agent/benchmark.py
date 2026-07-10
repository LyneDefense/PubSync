from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.prompts import anti_injection, output_schema, render_schema
from app.services.ai_service import create_json_response
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.platforms import PLATFORM_SPECS
from app.xhs_creation.schema import BenchmarkComparison

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
    system = f"""你是{platform_name}创作教练。把 <draft> 这篇用户草稿和 <benchmark_method>/<benchmark_stats> 里对标博主的方法论与数据画像做一次对比,评估它有多贴近对标博主的爆款套路,并指出还差哪些。用通俗中文,不要术语、不要代码。

{anti_injection("<benchmark_method>", "<benchmark_stats>", "<draft>")}

{output_schema(render_schema(BenchmarkComparison), preface="只输出 JSON:")}"""
    prompt = f"""<benchmark_method>
{ctx.skill.skill_markdown[:3500]}
</benchmark_method>
<benchmark_stats>
{json.dumps(stats_brief, ensure_ascii=False, default=str)[:2500]}
</benchmark_stats>
<draft>
{json.dumps(draft_brief, ensure_ascii=False, default=str)[:2500]}
</draft>"""
    try:
        data = create_json_response(settings, prompt, model=model, system=system)
    except Exception as exc:  # 对比失败不影响主产物
        logger.warning("对标对比生成失败:%s", exc)
        return {}
    # typed return:同一个 BenchmarkComparison 驱动 prompt schema(render_schema)与这里的解析校验。
    return BenchmarkComparison.model_validate(data if isinstance(data, dict) else {}).model_dump()


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
