import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSetting, NewsItem
from app.news_fetching import fetch_news
from app.news_processing import process_news_candidates
from app.services.ai_service import AIServiceError, is_ai_enabled


logger = logging.getLogger(__name__)


def fetch_latest_news(db: Session) -> list[NewsItem]:
    settings = get_settings()
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 provider，请设置 LLM_PROVIDER 和对应 API key")
    logger.info("新闻抓取流程开始")
    return fetch_ai_news(db)


def fetch_ai_news(db: Session) -> list[NewsItem]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    created_items: list[NewsItem] = []

    fetch_result = fetch_news(settings)
    candidates = fetch_result.candidates
    logger.info(
        "新闻候选准备完成：总数=%s，国际=%s，国内=%s",
        len(candidates),
        fetch_result.report.international_count,
        fetch_result.report.domestic_count,
    )

    processed_items = process_news_candidates(settings, candidates)
    logger.info("新闻后处理完成：可用条数=%s", len(processed_items))

    skipped_existing = 0
    skipped_invalid = 0
    for item in processed_items:
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip()
        if not url or not title or "example.com" in url:
            skipped_invalid += 1
            continue
        exists = db.scalar(select(NewsItem).where(NewsItem.url == url))
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
            title=title[:500],
            source=source,
            url=url[:1000],
            published_at=published_at,
            summary=summary,
            category=category,
            region=region,
            importance_score=importance_score,
            selected=importance_score >= 80,
        )
        db.add(news)
        created_items.append(news)

    db.merge(AppSetting(key="last_fetch_at", value=now.isoformat()))
    db.merge(AppSetting(key="last_fetch_report", value=json.dumps(fetch_result.report.to_dict(), ensure_ascii=False)))
    db.commit()

    for news in created_items:
        db.refresh(news)
    logger.info(
        "新闻抓取流程完成：新增=%s，跳过重复=%s，跳过无效=%s",
        len(created_items),
        skipped_existing,
        skipped_invalid,
    )
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
