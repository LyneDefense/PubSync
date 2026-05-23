import logging
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.article_composition import compose_article
from app.article_layout import render_basic_article_html, render_wechat_article_html
from app.article_selection import select_article_news
from app.config import get_settings
from app.models import Article, ArticleNewsItem, ArticleStatus, NewsItem
from app.services.ai_service import AIServiceError, decide_article_image, generate_image, is_ai_enabled


DEFAULT_COVER = "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80"
logger = logging.getLogger(__name__)


def generate_article_from_selected_news(db: Session) -> Article:
    settings = get_settings()
    selection = select_article_news(db, settings)
    selected_news = selection.news_items
    if not selected_news:
        raise ValueError(f"最近 {settings.article_news_lookback_hours} 小时内没有可生成文章的已选新闻")

    if is_ai_enabled(settings):
        title, intro, content_html, cover_image_url = generate_ai_article_content(settings, selected_news)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        title = normalize_article_title(f"{today} 重要动态")
        intro = f"今天精选 {len(selected_news)} 条 AI 行业大事件，覆盖模型、产品、基础设施和监管动态。"
        content_html = render_basic_article_html(intro, selected_news)
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
    news_payload = [
        {
            "index": index,
            "title": item.title,
            "source": item.source,
            "url": item.url,
            "published_at": item.published_at.isoformat(),
            "summary": item.summary,
            "category": item.category,
            "region": item.region,
            "importance_score": item.importance_score,
            "image_url": None,
        }
        for index, item in enumerate(selected_news)
    ]

    if settings.generate_article_images:
        apply_article_images(settings, selected_news, news_payload)

    composed_article = compose_article(settings, news_payload)
    content_html = render_wechat_article_html(composed_article)
    try:
        cover_image_url = generate_image(
            settings,
            composed_article.cover_prompt or build_cover_prompt(selected_news),
            "cover",
        )
    except AIServiceError:
        cover_image_url = None
    return (
        normalize_article_title(composed_article.title)[:300],
        composed_article.intro,
        content_html,
        cover_image_url or DEFAULT_COVER,
    )


def normalize_article_title(title: str) -> str:
    clean_title = " ".join(title.strip().split())
    prefix = "AI科技早报 | "
    if not clean_title:
        return f"{prefix}今日 AI 行业重要动态"
    if clean_title.startswith(prefix):
        return clean_title
    if clean_title.startswith("AI科技早报|"):
        return f"{prefix}{clean_title.split('|', 1)[1].strip()}"
    for stale_prefix in ("AI 早报：", "AI早报：", "AI科技早报："):
        if clean_title.startswith(stale_prefix):
            clean_title = clean_title.removeprefix(stale_prefix).strip()
            break
    return f"{prefix}{clean_title}"


def apply_article_images(settings, selected_news: list[NewsItem], news_payload: list[dict]) -> None:
    max_images = max(0, settings.max_article_images)
    min_images = max(0, min(settings.min_article_images, max_images))
    if max_images <= 0:
        return

    generated_indexes: set[int] = set()

    for index, news in enumerate(selected_news):
        if len(generated_indexes) >= max_images:
            break
        decision = decide_news_image(settings, news, forced=False)
        if not truthy(decision.get("should_generate")):
            continue
        if generate_news_image(settings, news, news_payload, index, decision, forced=False):
            generated_indexes.add(index)

    if len(generated_indexes) >= min_images:
        return

    for index, news in ranked_news_indexes(selected_news):
        if len(generated_indexes) >= min_images or len(generated_indexes) >= max_images:
            break
        if index in generated_indexes:
            continue
        decision = decide_news_image(settings, news, forced=True)
        if generate_news_image(settings, news, news_payload, index, decision, forced=True):
            generated_indexes.add(index)

    if len(generated_indexes) < min_images:
        logger.warning("article image generation below minimum generated=%s minimum=%s", len(generated_indexes), min_images)


def decide_news_image(settings, news: NewsItem, forced: bool) -> dict:
    payload = news_image_decision_payload(news)
    try:
        return decide_article_image(settings, payload, forced=forced)
    except AIServiceError as exc:
        logger.warning("article image decision failed news_id=%s forced=%s error=%s", news.id, forced, exc)
        if forced:
            return {"should_generate": True, "fallback_prompt": build_forced_news_image_prompt(news)}
        return {"should_generate": False, "fallback_prompt": build_forced_news_image_prompt(news)}


def generate_news_image(
    settings,
    news: NewsItem,
    news_payload: list[dict],
    index: int,
    decision: dict,
    forced: bool,
) -> bool:
    raw_prompt = str(decision.get("prompt") or decision.get("fallback_prompt") or "").strip()
    if forced and not raw_prompt:
        raw_prompt = build_forced_news_image_prompt(news)
    prompt = make_safe_image_prompt(raw_prompt)
    if not prompt or not is_safe_image_prompt(prompt):
        prompt = make_safe_image_prompt(build_forced_news_image_prompt(news))
    if not is_safe_image_prompt(prompt):
        logger.warning("article image prompt rejected news_id=%s forced=%s", news.id, forced)
        return False
    try:
        image_url = generate_image(settings, prompt, f"news-{news.id}")
    except AIServiceError as exc:
        logger.warning("article image generation failed news_id=%s forced=%s error=%s", news.id, forced, exc)
        return False
    if not image_url:
        return False
    news_payload[index]["image_url"] = image_url
    return True


def news_image_decision_payload(news: NewsItem) -> dict[str, object]:
    return {
        "title": news.title,
        "summary": news.summary,
        "category": news.category,
        "region": news.region,
        "source": news.source,
        "importance_score": news.importance_score,
    }


def ranked_news_indexes(news_items: list[NewsItem]) -> list[tuple[int, NewsItem]]:
    return sorted(
        enumerate(news_items),
        key=lambda pair: (pair[1].importance_score, pair[1].published_at),
        reverse=True,
    )


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "是", "需要"}
    return bool(value)


def is_safe_image_prompt(prompt: str) -> bool:
    lower = prompt.lower()
    required_negative_terms = ["no human", "no face", "no logo", "no brand"]
    risky_terms = [
        "portrait of",
        "realistic portrait",
        "human face",
        "company logo",
        "brand logo",
        "photorealistic photo of",
        "screenshot of",
    ]
    return all(term in lower for term in required_negative_terms) and not any(term in lower for term in risky_terms)


def make_safe_image_prompt(prompt: str) -> str:
    if not prompt:
        return ""
    safety_suffix = (
        " Abstract editorial infographic style. No human, no face, no celebrity, no real person, "
        "no fictional person, no logo, no brand mark, no photorealistic news scene, no UI screenshot, no text."
    )
    return f"{prompt.rstrip()} {safety_suffix}"


def build_forced_news_image_prompt(news: NewsItem) -> str:
    summary = " ".join(news.summary.split())[:220]
    return (
        "Editorial abstract technology infographic for an AI newsletter article. "
        f"Theme: {news.category}. "
        f"Represent the news as data flows, model layers, chips, cloud infrastructure, and network signals. "
        f"Use the article context without depicting named people, logos, screenshots, or real scenes. Context: {summary}. "
        "No human, no face, no celebrity, no real person, no fictional person, no logo, no brand mark, "
        "no photorealistic news scene, no UI screenshot, no text."
    )


def build_cover_prompt(news_items: list[NewsItem]) -> str:
    topics = "; ".join(item.title for item in news_items[:5])
    return (
        "Modern Chinese AI newsletter cover image, 16:9 composition, abstract technology infographic, "
        "no human, no face, no celebrity, no real person, no fictional person, no logo, no brand mark, "
        "no photorealistic news scene, no UI screenshot, no text, polished editorial style. Topics: "
        f"{topics}"
    )


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
