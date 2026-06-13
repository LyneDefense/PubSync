from __future__ import annotations

import json
from typing import Any

from app.account_audit.agent.context import AuditContext

# 固定的对标维度,保证结论结构稳定、可比。
AUDIT_DIMENSIONS = ["选题", "标题", "结构", "表达/语言", "互动/CTA"]


def build_audit_prompt(ctx: AuditContext) -> str:
    """构造账号体检提示词:对照对标博主方法论 + 数据画像,诊断用户自己的内容。"""
    stats_brief = _stats_brief(ctx.benchmark_stats)
    dims = "、".join(AUDIT_DIMENSIONS)
    return f"""
你是{ctx.platform_name}账号增长顾问。下面给你两样东西:
1)一位对标博主蒸馏出的方法论(以及他的数据画像);
2)用户自己账号最近的一些内容。

请像一面镜子:把用户的内容和对标博主逐维度对比({dims}),指出用户已经做对的、明显的短板、
以及可以立即执行的改进动作,最后给一个总体结论和一个 0-100 的「对标接近度」分数(越高=越接近对标博主的打法)。

要求:
- 通俗、具体、可执行;每条都贴着实际内容说话,不要正确的废话、不要术语堆砌。
- 只点评创作方法,不要冒充谁,也不要编造用户没写过的东西。
- 输出必须是合法 JSON,不要 Markdown、不要解释过程。

对标博主方法论:
{ctx.skill_markdown[:9000]}

对标博主数据画像:
{json.dumps(stats_brief, ensure_ascii=False, default=str)[:2500]}

用户自己账号的内容:
{ctx.my_content[:8000]}

只输出下面这个 JSON:
{{
  "dimensions": [
    {{"name": "维度名(选题/标题/结构/表达语言/互动CTA)", "benchmark": "对标博主在这维度怎么做", "mine": "用户现在怎么做", "gap": "差距与具体改法"}}
  ],
  "strengths": ["用户已经做对的地方"],
  "gaps": ["用户明显的短板"],
  "actions": ["立即可执行的改进动作"],
  "conclusion": "一段话总体结论:离对标博主还有多远、最该先补哪里",
  "score": 0
}}
"""


def normalize_audit_output(data: dict[str, Any], ctx: AuditContext) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    dimensions = data.get("dimensions")
    clean_dims: list[dict[str, str]] = []
    if isinstance(dimensions, list):
        for item in dimensions:
            if isinstance(item, dict):
                clean_dims.append(
                    {
                        "name": str(item.get("name") or "").strip(),
                        "benchmark": str(item.get("benchmark") or "").strip(),
                        "mine": str(item.get("mine") or "").strip(),
                        "gap": str(item.get("gap") or "").strip(),
                    }
                )
    data["dimensions"] = clean_dims
    for key in ("strengths", "gaps", "actions"):
        value = data.get(key)
        data[key] = [str(x).strip() for x in value if str(x).strip()] if isinstance(value, list) else []
    data["conclusion"] = str(data.get("conclusion") or "").strip()
    try:
        data["score"] = max(0, min(100, int(data.get("score"))))
    except (TypeError, ValueError):
        data["score"] = None
    return data


def _stats_brief(stats: dict[str, Any]) -> dict[str, Any]:
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
    return brief
