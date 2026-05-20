from datetime import datetime
from html import escape

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Article, ArticleNewsItem, ArticleStatus, NewsItem


DEFAULT_COVER = "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80"


def generate_article_from_selected_news(db: Session) -> Article:
    selected_news = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.selected.is_(True))
            .order_by(NewsItem.importance_score.desc(), NewsItem.published_at.desc())
            .limit(10)
        )
    )
    if not selected_news:
        raise ValueError("请先选择至少一条新闻")

    today = datetime.now().strftime("%Y-%m-%d")
    title = f"AI 早报：{today} 重要动态"
    intro = f"今天精选 {len(selected_news)} 条 AI 行业大事件，覆盖模型、产品、基础设施和监管动态。"
    content_html = render_article_html(intro, selected_news)

    article = Article(
        title=title,
        intro=intro,
        content_html=content_html,
        cover_image_url=DEFAULT_COVER,
        status=ArticleStatus.generated,
    )
    db.add(article)
    db.flush()

    for position, news in enumerate(selected_news, start=1):
        db.add(ArticleNewsItem(article_id=article.id, news_item_id=news.id, position=position))

    db.commit()
    db.refresh(article)
    return article


def render_article_html(intro: str, news_items: list[NewsItem]) -> str:
    sections = [
        "<section>",
        f"<p>{escape(intro)}</p>",
        "</section>",
    ]
    for index, item in enumerate(news_items, start=1):
        sections.extend(
            [
                "<section style=\"margin-top: 24px;\">",
                f"<h2>{index}. {escape(item.title)}</h2>",
                f"<p><strong>{escape(item.category)}</strong> · {escape(item.source)} · 重要性 {item.importance_score}/100</p>",
                f"<p>{escape(item.summary)}</p>",
                f"<p>来源：<a href=\"{escape(item.url)}\">{escape(item.url)}</a></p>",
                "</section>",
            ]
        )

    sections.append("<p style=\"margin-top: 32px; color: #666;\">以上内容由 PubSync 自动整理，发布前请人工核对来源和事实。</p>")
    return "\n".join(sections)


def update_article(db: Session, article: Article, **values: str | None) -> Article:
    for key, value in values.items():
        if value is not None:
            setattr(article, key, value)
    db.commit()
    db.refresh(article)
    return article


def replace_article_items(db: Session, article: Article, news_ids: list[int]) -> Article:
    db.execute(delete(ArticleNewsItem).where(ArticleNewsItem.article_id == article.id))
    for position, news_id in enumerate(news_ids, start=1):
        db.add(ArticleNewsItem(article_id=article.id, news_item_id=news_id, position=position))
    db.commit()
    db.refresh(article)
    return article
