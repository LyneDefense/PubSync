from __future__ import annotations

from typing import Any

from app.account_audit.agent.context import AuditContext

# 固定的对标维度,保证结论结构稳定、可比。
AUDIT_DIMENSIONS = ["选题", "标题", "结构", "表达/语言", "互动/CTA"]


def build_audit_prompt(ctx: AuditContext) -> str:
    """按 kind 选提示词:benchmark=逐维度对比;self=自我诊断。"""
    if ctx.kind == "self":
        return _build_self_prompt(ctx)
    return _build_benchmark_prompt(ctx)


def _build_benchmark_prompt(ctx: AuditContext) -> str:
    dims = "、".join(AUDIT_DIMENSIONS)
    return f"""
你是{ctx.platform_name}账号增长顾问。下面给你两个账号最近的真实内容:
1)用户自己账号「{ctx.my_name}」的内容;
2)对标账号「{ctx.benchmark_name}」的内容。

请像一面镜子:把用户的内容和对标账号逐维度对比({dims}),指出用户已经做对的、明显的短板、
以及可以立即执行的改进动作,最后给一段总体结论和一个 0-100 的「对标接近度」分数(越高=越接近对标账号的打法)。

要求:
- 通俗、具体、可执行;每条都贴着实际内容说话,不要正确的废话、不要术语堆砌。
- 只点评创作方法,不要冒充谁,也不要编造没出现过的内容。
- 输出必须是合法 JSON,不要 Markdown、不要解释过程。

我的账号内容:
{ctx.my_content[:8000]}

对标账号内容:
{ctx.benchmark_content[:8000]}

只输出下面这个 JSON:
{{
  "dimensions": [
    {{"name": "维度名(选题/标题/结构/表达语言/互动CTA)", "benchmark": "对标账号在这维度怎么做", "mine": "我现在怎么做", "gap": "差距与具体改法"}}
  ],
  "strengths": ["我已经做对的地方"],
  "gaps": ["我明显的短板"],
  "actions": ["立即可执行的改进动作"],
  "conclusion": "一段话总体结论:离对标账号还有多远、最该先补哪里",
  "score": 0
}}
"""


def _build_self_prompt(ctx: AuditContext) -> str:
    return f"""
你是{ctx.platform_name}账号增长顾问。下面是用户自己账号「{ctx.my_name}」最近的真实内容。

请像一面镜子,只针对这个账号本身做诊断:指出账号已经做对的地方(优势)、明显的短板,
以及可以立即执行的增长动作,最后给一段总体结论和一个 0-100 的「账号健康度」分数。

要求:
- 通俗、具体、可执行;每条都贴着实际内容说话,不要正确的废话、不要术语堆砌。
- 不要冒充谁,也不要编造账号没出现过的内容。
- 输出必须是合法 JSON,不要 Markdown、不要解释过程。

我的账号内容:
{ctx.my_content[:9000]}

只输出下面这个 JSON:
{{
  "strengths": ["账号已经做对的地方"],
  "gaps": ["明显的短板"],
  "actions": ["立即可执行的增长动作"],
  "conclusion": "一段话总体结论:当前账号最该先补哪里",
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
