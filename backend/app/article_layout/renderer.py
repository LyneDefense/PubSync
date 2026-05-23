from html import escape

from app.article_composition.models import ArticleSection, ComposedArticle
from app.article_layout.wechat_formatter import format_wechat_article_html
from app.models import NewsItem


def render_wechat_article_html(article: ComposedArticle) -> str:
    parts = [
        "<section>",
        f"<p>{escape(article.intro)}</p>",
        "</section>",
    ]
    for section in article.sections:
        parts.extend(render_section(section))
    return format_wechat_article_html("\n".join(parts))


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
    return format_wechat_article_html("\n".join(parts))
