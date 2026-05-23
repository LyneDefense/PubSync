from typing import Any

from app.article_composition.models import ArticleSection, ComposedArticle


def validate_composed_article(raw_data: object, news_items: list[dict[str, Any]]) -> ComposedArticle:
    if not isinstance(raw_data, dict):
        raise ValueError("AI 文章生成返回不是对象")

    title = normalize_text(raw_data.get("title"), "AI科技早报 | 今日 AI 行业重要动态")[:300]
    intro = normalize_text(raw_data.get("intro"), "")[:500]
    cover_prompt = normalize_text(raw_data.get("cover_prompt"), "")
    raw_sections = raw_data.get("sections")
    if not isinstance(raw_sections, list):
        raw_sections = []

    sections: list[ArticleSection] = []
    used_indexes: set[int] = set()
    for raw_section in raw_sections:
        section = normalize_section(raw_section, news_items, used_indexes)
        if section:
            sections.append(section)
            used_indexes.add(section.news_index)

    for index, item in enumerate(news_items):
        if index not in used_indexes:
            sections.append(fallback_section(index, item))

    if not intro and sections:
        intro = sections[0].paragraphs[0][:120]

    return ComposedArticle(
        title=title,
        intro=intro or "今天精选 AI 行业重要动态，梳理技术、产品和产业变化。",
        cover_prompt=cover_prompt,
        sections=sections,
    )


def normalize_section(
    raw_section: object,
    news_items: list[dict[str, Any]],
    used_indexes: set[int],
) -> ArticleSection | None:
    if not isinstance(raw_section, dict):
        return None
    try:
        news_index = int(raw_section.get("news_index"))
    except (TypeError, ValueError):
        return None
    if news_index < 0 or news_index >= len(news_items) or news_index in used_indexes:
        return None

    item = news_items[news_index]
    heading = normalize_text(raw_section.get("heading"), f"{news_index + 1:02d}｜{item.get('title', 'AI 动态')}")[:120]
    paragraphs = normalize_paragraphs(raw_section.get("paragraphs"), str(item.get("summary") or ""))
    editor_note = normalize_text(raw_section.get("editor_note"), "这条动态值得关注的是，它反映了 AI 技术从能力展示走向真实应用的持续变化。")
    return ArticleSection(
        news_index=news_index,
        group_key=str(item.get("group_key") or "main").strip() or "main",
        group_name=str(item.get("group_name") or "精选内容").strip() or "精选内容",
        heading=heading,
        paragraphs=paragraphs,
        editor_note=editor_note,
        image_url=str(item.get("image_url") or "").strip(),
        source_name=str(item.get("source") or "来源").strip(),
        source_url=str(item.get("url") or "").strip(),
    )


def fallback_section(index: int, item: dict[str, Any]) -> ArticleSection:
    summary = normalize_text(item.get("summary"), "这条 AI 动态值得关注。")
    content_mode = str(item.get("content_mode") or "news")
    return ArticleSection(
        news_index=index,
        group_key=str(item.get("group_key") or "main").strip() or "main",
        group_name=str(item.get("group_name") or "精选内容").strip() or "精选内容",
        heading=f"{index + 1:02d}｜{normalize_text(item.get('title'), 'AI 动态')[:80]}",
        paragraphs=fallback_paragraphs(summary, content_mode),
        editor_note=fallback_editor_note(content_mode),
        image_url=str(item.get("image_url") or "").strip(),
        source_name=str(item.get("source") or "来源").strip(),
        source_url=str(item.get("url") or "").strip(),
    )


def fallback_paragraphs(summary: str, content_mode: str) -> list[str]:
    if content_mode == "knowledge":
        return [
            summary,
            "从日常养护角度看，这类内容更适合转化成可执行的提醒：先判断宠物年龄、体况、饮食和近期行为变化，再决定是否调整护理方式。",
            "如果涉及健康风险、用药、营养补充或持续异常，建议把它当作科普信息参考，并结合兽医建议做具体决策。",
        ]
    if content_mode == "analysis":
        return [
            summary,
            "这背后反映的是宠物消费、医疗服务和内容需求正在继续细分，品牌和门店需要把专业可信与用户体验同时做好。",
        ]
    return [summary]


def fallback_editor_note(content_mode: str) -> str:
    if content_mode == "knowledge":
        return "编辑观察：知识分享的价值不在于制造焦虑，而是帮助读者把复杂信息转化成更稳妥的日常判断。"
    if content_mode == "analysis":
        return "编辑观察：这类变化值得关注，因为它可能影响宠物服务供给、用户信任和行业竞争方式。"
    return "编辑观察：这条动态值得关注的是，它可能影响后续产品落地、开发者生态或行业竞争格局。"


def normalize_paragraphs(value: object, fallback: str) -> list[str]:
    if not isinstance(value, list):
        return [normalize_text(fallback, "暂无摘要")]
    paragraphs = [normalize_text(item, "") for item in value]
    paragraphs = [item for item in paragraphs if item]
    return paragraphs[:5] or [normalize_text(fallback, "暂无摘要")]


def normalize_text(value: object, default: str) -> str:
    if isinstance(value, list):
        value = "；".join(str(item) for item in value if item)
    if not isinstance(value, str):
        return default
    text = " ".join(value.strip().split())
    return text or default
