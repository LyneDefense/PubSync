import logging
from html import escape

from app.article_composition.models import ArticleSection, ComposedArticle
from app.article_layout.wechat_formatter import format_wechat_article_html
from app.models import NewsItem


logger = logging.getLogger(__name__)


def render_wechat_article_html(article: ComposedArticle) -> str:
    logger.info("文章排版开始：段落数=%s", len(article.sections))
    parts = [
        "<section>",
        f"<p>{escape(article.intro)}</p>",
        "</section>",
    ]
    for label, sections in grouped_sections(article.sections):
        if sections:
            parts.extend(["<section>", f"<h2>{escape(label)}</h2>", "</section>"])
            for section in sections:
                parts.extend(render_section(section))
    html = format_wechat_article_html("\n".join(parts))
    logger.info("文章排版完成：页面字符数=%s", len(html))
    return html


def grouped_sections(sections: list[ArticleSection]) -> list[tuple[str, list[ArticleSection]]]:
    international = [section for section in sections if section.region != "domestic"]
    domestic = [section for section in sections if section.region == "domestic"]
    if international and domestic:
        return [("国际动态", international), ("国内动态", domestic)]
    if domestic:
        return [("国内动态", domestic)]
    return [("国际动态", international)]


def render_section(section: ArticleSection) -> list[str]:
    parts = [
        "<section>",
        f"<h2>{escape(section.heading)}</h2>",
    ]
    for index, paragraph in enumerate(section.paragraphs):
        parts.append(f"<p>{escape(paragraph)}</p>")
        if index == 0 and section.image_url:
            parts.append(f'<img src="{escape(section.image_url, quote=True)}" alt="文章配图" />')
    if section.editor_note:
        parts.append(f"<blockquote>{escape(section.editor_note)}</blockquote>")
    if section.source_url:
        parts.append(
            f'<p>来源：<a href="{escape(section.source_url, quote=True)}">{escape(section.source_name or "来源")}</a></p>'
        )
    parts.append("</section>")
    return parts


def render_basic_article_html(intro: str, news_items: list[NewsItem]) -> str:
    logger.info("基础文章排版开始：新闻数=%s", len(news_items))
    parts = [
        "<section>",
        f"<p>{escape(intro)}</p>",
        "</section>",
    ]
    for index, item in enumerate(news_items, start=1):
        parts.extend(
            [
                "<section>",
                f"<h2>{index:02d}｜{escape(item.title)}</h2>",
                f"<p>{escape(item.summary)}</p>",
                f'<p>来源：<a href="{escape(item.url, quote=True)}">{escape(item.source)}</a></p>',
                "</section>",
            ]
        )
    html = format_wechat_article_html("\n".join(parts))
    logger.info("基础文章排版完成：页面字符数=%s", len(html))
    return html
