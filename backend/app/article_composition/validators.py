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
    return ArticleSection(
        news_index=index,
        group_key=str(item.get("group_key") or "main").strip() or "main",
        group_name=str(item.get("group_name") or "精选内容").strip() or "精选内容",
        heading=f"{index + 1:02d}｜{normalize_text(item.get('title'), 'AI 动态')[:80]}",
        paragraphs=[summary],
        editor_note="这条动态值得关注的是，它可能影响后续产品落地、开发者生态或行业竞争格局。",
        image_url=str(item.get("image_url") or "").strip(),
        source_name=str(item.get("source") or "来源").strip(),
        source_url=str(item.get("url") or "").strip(),
    )


def normalize_paragraphs(value: object, fallback: str) -> list[str]:
    if not isinstance(value, list):
        return [normalize_text(fallback, "暂无摘要")]
    paragraphs = [normalize_text(item, "") for item in value]
    paragraphs = [item for item in paragraphs if item]
    return paragraphs[:3] or [normalize_text(fallback, "暂无摘要")]


def normalize_text(value: object, default: str) -> str:
    if isinstance(value, list):
        value = "；".join(str(item) for item in value if item)
    if not isinstance(value, str):
        return default
    text = " ".join(value.strip().split())
    return text or default
