import json

from app.news_fetching.models import RawNewsCandidate


def build_news_processing_prompt(candidates: list[RawNewsCandidate]) -> str:
    prompt_candidates = [candidate.to_prompt_dict() for candidate in candidates]
    return f"""
你是一个严谨的 AI 行业新闻编辑。下面是代码从 RSS/Atom 源抓到的候选新闻。

你的职责是后处理，不是抓取新闻：
- 只能基于候选新闻中的 title、summary、source、region、url、published_at 进行判断。
- 不要编造候选集中不存在的新闻、URL、融资金额、发布日期、产品能力或人物观点。
- 对候选做事件级去重：多条候选报道同一事件时，只保留信息最完整、最权威或发布时间最合适的一条作为 candidate_id，其他放入 duplicate_candidate_ids。
- 分别关注 international 和 domestic 新闻。国际候选通常选择 5-8 条，国内候选通常选择 3-5 条；如果某一区域候选质量不足，可以少选，不要用低质量新闻凑数。
- 排除广告稿、低质量转载、招聘/活动营销、无法判断事实主体的内容。
- display_title 可以改写为中文标题，但不能改变事实。
- summary 用 2-3 句中文，包含事实、影响和背景，不要夸大。
- category 只能从这些值中选择：模型发布、研究进展、企业应用、开源项目、基础设施、开发者工具、产品更新、政策监管、资本市场、行业观察。
- importance_score 按下面标准打分：
  - 95-100：全球或国内 AI 行业重大事件，影响多个公司、开发者生态或监管方向。
  - 90-94：头部公司、重要模型、资本、监管、基础设施重大进展。
  - 80-89：值得进入早报的重要产品、研究、商业或开源动态。
  - 70-79：备选新闻，有价值但影响范围有限。
  - 70 以下：不要返回。
- 不要所有新闻都给高分；每天只有少数新闻应超过 92。

候选新闻：
{json.dumps(prompt_candidates, ensure_ascii=False, indent=2)}

输出 JSON，格式为：
{{
  "items": [
    {{
      "candidate_id": "c_001",
      "duplicate_candidate_ids": ["c_004", "c_009"],
      "display_title": "中文展示标题",
      "summary": "2-3 句中文摘要",
      "category": "模型发布",
      "importance_score": 90,
      "importance_reason": "为什么值得进入早报",
      "key_facts": ["事实1", "事实2", "事实3"]
    }}
  ]
}}
"""
