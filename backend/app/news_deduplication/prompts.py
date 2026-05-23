import json
from typing import Any


def build_duplicate_review_prompt(candidate: dict[str, Any], existing: dict[str, Any], similarity: float) -> str:
    return f"""
你是严谨的新闻去重编辑。请判断“候选新闻”和“历史新闻”是否报道同一个核心事件。

判定标准：
- 如果只是同一家公司、同一行业、同一主题，但事件不同，不算重复。
- 如果核心事实、时间线和主要动作一致，即使标题、来源、语言不同，也算重复。
- 如果候选新闻只是历史新闻的转载、跟进报道或轻微改写，并没有新增关键事实，算重复。
- 如果候选新闻包含新的重大进展、监管结果、产品发布细节、融资金额变化等实质新增事实，不算重复。

相似度参考：{similarity:.3f}

候选新闻：
{json.dumps(candidate, ensure_ascii=False, indent=2)}

历史新闻：
{json.dumps(existing, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "is_duplicate": true,
  "reason": "简短说明为什么是或不是同一事件"
}}
"""
