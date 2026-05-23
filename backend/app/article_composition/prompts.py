import json
from typing import Any


def build_article_composition_prompt(
    news_items: list[dict[str, Any]],
    profile: Any | None = None,
    content_groups: list | None = None,
) -> str:
    publication_name = getattr(profile, "publication_name", "AI 科技早报")
    title_prefix = getattr(profile, "title_prefix", "AI科技早报 | ")
    content_domain = getattr(profile, "content_domain", "AI、科技、模型、算力、企业应用")
    editor_persona = getattr(profile, "editor_persona", "你是微信公众号 AI 科技早报主编")
    audience = getattr(profile, "audience", "科技从业者、产品经理、投资人与 AI 关注者")
    article_style = getattr(profile, "article_style", "信息密度高，事实准确，带行业观察")
    image_style = getattr(profile, "image_style", "抽象科技视觉、信息图、芯片、网络、云与模型架构")
    grouping_mode = getattr(profile, "grouping_mode", "regional")
    groups = [group for group in (content_groups or []) if getattr(group, "enabled", True)]
    group_description = "，".join(
        f"{group.group_key}={group.name}，内容形态={content_mode_label(getattr(group, 'content_mode', 'news'))}"
        for group in groups
    ) or "main=精选内容"
    grouping_instruction = (
        f"排版层会自动按 group_key 渲染分组标题，可用分组为：{group_description}。你不要在 heading 或正文里重复输出分组标题。"
        if grouping_mode == "regional"
        else "当前栏目不按分组组织内容，sections 只需要尊重新闻推荐顺序，不要输出分组标题。"
    )
    return f"""
{editor_persona}。请基于下面的新闻事实生成一篇中文公众号草稿的结构化内容。

你的职责是写内容，不是写 HTML：
- 不能改变新闻事实，不能编造来源、融资金额、发布日期、产品能力或人物观点。
- 可以做编辑化提炼、背景解释、影响分析，但事实和判断要区分。
- 当前公众号/栏目：{publication_name}。
- 当前内容领域：{content_domain}。
- 目标读者：{audience}。
- 文章风格：{article_style}。
- 标题必须输出“{title_prefix}xxx”格式，xxx 是你生成的标题内容；不要使用其他前缀。
- 开头先写 1 段 80-140 字导语，说明今天最重要的主线。
- 新闻事实中的 group_key 只用于组织内容；不要直接输出 group_key 等内部字段。
- 新闻事实已经按推荐顺序排列，sections 应尊重这个顺序。
- {grouping_instruction}
- 根据每条素材的 content_mode 决定写法：
  - news：写成资讯解读，至少包含“发生了什么”“为什么重要”“编辑观察”三个层次；建议 220-360 个中文字，输出 2-3 段。
  - knowledge：写成长一点的知识分享/科普指南，重点解释概念、适用场景、实操建议、注意事项；建议 420-700 个中文字，输出 3-5 段。可以围绕主题做常识性延展，但不能编造具体研究、病例、数据或来源。
  - analysis：写成行业观察，重点写背景、趋势、商业影响、经营启发；建议 320-520 个中文字，输出 3-4 段。
- 每段 paragraphs 建议 80-150 个中文字。
- editor_note 写 1 句编辑观察，避免套话，不能展示内部评分、分类、候选池排序等后台筛选信息。
- heading 使用“01｜新闻标题”这种编号格式，不要重复写过长标题。
- 每条输入新闻都必须生成一个 section，不要漏掉，也不要新增输入之外的新闻。
- 不要输出 HTML、Markdown、CSS、表格或列表符号，只输出 JSON。

新闻事实：
{json.dumps(news_items, ensure_ascii=False, indent=2)}

输出 JSON，格式为：
{{
  "title": "{title_prefix}不超过 64 字的公众号标题",
  "intro": "不超过 120 字的摘要导语",
  "cover_prompt": "英文封面图提示词，视觉方向：{image_style}；禁止真实人物肖像、虚构人物肖像、真实 logo、仿新闻现场照片",
  "sections": [
    {{
      "news_index": 0,
      "heading": "01｜新闻标题",
      "paragraphs": ["正文段落1", "正文段落2"],
      "editor_note": "编辑观察"
    }}
  ]
}}
"""


def content_mode_label(mode: str) -> str:
    return {
        "news": "新闻资讯",
        "knowledge": "知识分享",
        "analysis": "行业观察",
    }.get(mode, "新闻资讯")
