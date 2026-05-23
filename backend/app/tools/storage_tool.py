import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, Article, ArticleNewsItem, ArticleStatus, NewsItem
from app.news_fetching.models import NewsFetchResult


def persist_processed_news(
    db: Session,
    tenant_id: int,
    fetch_result: NewsFetchResult,
    processed_items: list[dict[str, Any]],
) -> tuple[list[NewsItem], int, int]:
    now = datetime.now(timezone.utc)
    created_items: list[NewsItem] = []
    skipped_existing = 0
    skipped_invalid = 0

    for item in processed_items:
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip()
        if not url or not title or "example.com" in url:
            skipped_invalid += 1
            continue
        exists = db.scalar(select(NewsItem).where(NewsItem.tenant_id == tenant_id, NewsItem.url == url))
        if exists:
            skipped_existing += 1
            continue

        importance_score = normalize_score(item.get("importance_score"))
        if importance_score is None:
            skipped_invalid += 1
            continue
        published_at = parse_datetime(item.get("published_at")) or now
        summary = normalize_text(item.get("summary"), default="暂无摘要")
        category = normalize_text(item.get("category"), default="AI 动态")[:80]
        region = normalize_region(item.get("region"))
        source = normalize_text(item.get("source"), default="Unknown")[:200]

        news = NewsItem(
            tenant_id=tenant_id,
            title=title[:500],
            source=source,
            url=url[:1000],
            published_at=published_at,
            summary=summary,
            category=category,
            region=region,
            importance_score=importance_score,
            selected=importance_score >= 80,
            dedup_key=str(item.get("_dedup_key") or "")[:200] or None,
            dedup_status="unique",
            dedup_reason="去重后保留",
        )
        db.add(news)
        created_items.append(news)

    db.merge(AppSetting(key=f"tenant:{tenant_id}:last_fetch_at", tenant_id=tenant_id, value=now.isoformat()))
    db.merge(
        AppSetting(
            key=f"tenant:{tenant_id}:last_fetch_report",
            tenant_id=tenant_id,
            value=json.dumps(fetch_result.report.to_dict(), ensure_ascii=False),
        )
    )
    db.commit()

    for news in created_items:
        db.refresh(news)
    return created_items, skipped_existing, skipped_invalid


def persist_article(
    db: Session,
    tenant_id: int,
    title: str,
    intro: str,
    content_html: str,
    cover_image_url: str,
    selected_news: list[NewsItem],
) -> Article:
    article = Article(
        tenant_id=tenant_id,
        title=title,
        intro=intro,
        content_html=content_html,
        cover_image_url=cover_image_url,
        status=ArticleStatus.generated,
    )
    db.add(article)
    db.flush()

    for position, news in enumerate(selected_news, start=1):
        db.add(ArticleNewsItem(article_id=article.id, news_item_id=news.id, tenant_id=tenant_id, position=position))

    db.commit()
    db.refresh(article)
    return article


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def normalize_score(value: object) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, score))


def normalize_region(value: object) -> str:
    region = str(value or "").strip().lower()
    if region in {"domestic", "international"}:
        return region
    return "international"


def normalize_text(value: object, default: str) -> str:
    if isinstance(value, list):
        value = "；".join(str(item) for item in value if item)
    if not isinstance(value, str):
        return default
    text = value.strip()
    return text or default
