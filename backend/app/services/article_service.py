from datetime import datetime
from html import escape

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Article, ArticleNewsItem, ArticleStatus, NewsItem
from app.services.ai_service import AIServiceError, generate_image, generate_wechat_article, is_ai_enabled


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

    settings = get_settings()
    if is_ai_enabled(settings):
        title, intro, content_html, cover_image_url = generate_ai_article_content(settings, selected_news)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        title = f"AI 早报：{today} 重要动态"
        intro = f"今天精选 {len(selected_news)} 条 AI 行业大事件，覆盖模型、产品、基础设施和监管动态。"
        content_html = render_article_html(intro, selected_news)
        cover_image_url = DEFAULT_COVER

    article = Article(
        title=title,
        intro=intro,
        content_html=content_html,
        cover_image_url=cover_image_url,
        status=ArticleStatus.generated,
    )
    db.add(article)
    db.flush()

    for position, news in enumerate(selected_news, start=1):
        db.add(ArticleNewsItem(article_id=article.id, news_item_id=news.id, position=position))

    db.commit()
    db.refresh(article)
    return article


def generate_ai_article_content(settings, selected_news: list[NewsItem]) -> tuple[str, str, str, str]:
    news_payload = []
    max_images = max(0, settings.max_article_images)
    for index, item in enumerate(selected_news):
        image_url = None
        if settings.generate_article_images and index < max_images:
            try:
                image_url = generate_image(
                    settings,
                    build_news_image_prompt(item),
                    f"news-{item.id}",
                )
            except AIServiceError:
                image_url = None
        news_payload.append(
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_at": item.published_at.isoformat(),
                "summary": item.summary,
                "category": item.category,
                "importance_score": item.importance_score,
                "image_url": image_url,
            }
        )

    article_data = generate_wechat_article(settings, news_payload)
    try:
        cover_image_url = generate_image(
            settings,
            str(article_data.get("cover_prompt") or build_cover_prompt(selected_news)),
            "cover",
        )
    except AIServiceError:
        cover_image_url = None
    return (
        str(article_data["title"])[:300],
        str(article_data["intro"]),
        str(article_data["content_html"]),
        cover_image_url or DEFAULT_COVER,
    )


def build_news_image_prompt(item: NewsItem) -> str:
    return (
        "Editorial technology illustration, 16:9 composition, no real person, no real logo, "
        f"topic: {item.title}. Context: {item.summary}. "
        "Clean modern AI newsletter style, suitable for WeChat article section image."
    )


def build_cover_prompt(news_items: list[NewsItem]) -> str:
    topics = "; ".join(item.title for item in news_items[:5])
    return (
        "Modern Chinese AI newsletter cover image, 16:9 composition, abstract technology visuals, "
        "no real person, no real company logo, polished editorial style. Topics: "
        f"{topics}"
    )


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
