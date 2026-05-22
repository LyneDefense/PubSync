from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSetting, NewsItem
from app.news_fetching import fetch_news_candidates
from app.news_processing import process_news_candidates
from app.services.ai_service import AIServiceError, is_ai_enabled


def fetch_latest_news(db: Session) -> list[NewsItem]:
    settings = get_settings()
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 provider，请设置 LLM_PROVIDER 和对应 API key")
    return fetch_ai_news(db)


def fetch_ai_news(db: Session) -> list[NewsItem]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    created_items: list[NewsItem] = []

    candidates = fetch_news_candidates(settings)
    for item in process_news_candidates(settings, candidates):
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip()
        if not url or not title or "example.com" in url:
            continue
        exists = db.scalar(select(NewsItem).where(NewsItem.url == url))
        if exists:
            continue

        importance_score = normalize_score(item.get("importance_score"))
        published_at = parse_datetime(item.get("published_at")) or now
        summary = normalize_text(item.get("summary"), default="暂无摘要")
        category = normalize_text(item.get("category"), default="AI 动态")[:80]
        source = normalize_text(item.get("source"), default="Unknown")[:200]

        news = NewsItem(
            title=title[:500],
            source=source,
            url=url[:1000],
            published_at=published_at,
            summary=summary,
            category=category,
            importance_score=importance_score,
            selected=importance_score >= 80,
        )
        db.add(news)
        created_items.append(news)

    db.merge(AppSetting(key="last_fetch_at", value=now.isoformat()))
    db.commit()

    for news in created_items:
        db.refresh(news)
    return created_items


def list_news(db: Session) -> list[NewsItem]:
    return list(
        db.scalars(
            select(NewsItem).order_by(
                NewsItem.selected.desc(),
                NewsItem.importance_score.desc(),
                NewsItem.published_at.desc(),
            )
        )
    )


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


def normalize_score(value: object) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 70
    return max(0, min(100, score))


def normalize_text(value: object, default: str) -> str:
    if isinstance(value, list):
        value = "；".join(str(item) for item in value if item)
    if not isinstance(value, str):
        return default
    text = value.strip()
    return text or default
