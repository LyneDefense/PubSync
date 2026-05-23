import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.article_selection.models import ArticleSelectionResult, RegionSelectionRule
from app.config import Settings
from app.models import NewsItem


DOMESTIC = "domestic"
INTERNATIONAL = "international"
logger = logging.getLogger(__name__)


def select_article_news(db: Session, settings: Settings) -> ArticleSelectionResult:
    article_limit = max(1, settings.article_news_limit)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, settings.article_news_lookback_hours))
    logger.info(
        "文章新闻选择开始：数量上限=%s，回看小时=%s",
        article_limit,
        settings.article_news_lookback_hours,
    )
    domestic_rule = RegionSelectionRule(
        region=DOMESTIC,
        minimum=settings.article_domestic_min,
        target=settings.article_domestic_target,
        maximum=settings.article_domestic_max,
    ).normalized(article_limit)
    international_rule = RegionSelectionRule(
        region=INTERNATIONAL,
        minimum=settings.article_international_min,
        target=settings.article_international_target,
        maximum=settings.article_international_max,
    ).normalized(article_limit)
    domestic_rule, international_rule = fit_targets_to_limit(domestic_rule, international_rule, article_limit)

    domestic_pool = fetch_region_pool(db, domestic_rule.region, cutoff, domestic_rule.maximum)
    international_pool = fetch_region_pool(db, international_rule.region, cutoff, international_rule.maximum)
    logger.info(
        "文章新闻候选池准备完成：国际=%s，国内=%s",
        len(international_pool),
        len(domestic_pool),
    )

    selected_domestic = domestic_pool[: domestic_rule.target]
    selected_international = international_pool[: international_rule.target]

    selected_domestic, selected_international = fill_selection(
        selected_domestic=selected_domestic,
        selected_international=selected_international,
        domestic_pool=domestic_pool,
        international_pool=international_pool,
        domestic_rule=domestic_rule,
        international_rule=international_rule,
        article_limit=article_limit,
    )

    news_items = [*selected_international, *selected_domestic]
    logger.info(
        "文章新闻选择完成：总数=%s，国际=%s，国内=%s，可用候选=%s",
        len(news_items[:article_limit]),
        len(selected_international),
        len(selected_domestic),
        len(domestic_pool) + len(international_pool),
    )
    return ArticleSelectionResult(
        news_items=news_items[:article_limit],
        domestic_count=len(selected_domestic),
        international_count=len(selected_international),
        total_available=len(domestic_pool) + len(international_pool),
    )


def fit_targets_to_limit(
    domestic_rule: RegionSelectionRule,
    international_rule: RegionSelectionRule,
    article_limit: int,
) -> tuple[RegionSelectionRule, RegionSelectionRule]:
    if domestic_rule.target + international_rule.target <= article_limit:
        return domestic_rule, international_rule

    domestic_target = min(domestic_rule.target, article_limit)
    international_target = min(international_rule.target, max(0, article_limit - domestic_target))
    if (
        international_target < international_rule.minimum
        and article_limit >= domestic_rule.minimum + international_rule.minimum
    ):
        international_target = international_rule.minimum
        domestic_target = min(domestic_rule.target, article_limit - international_target)

    return (
        RegionSelectionRule(
            region=domestic_rule.region,
            minimum=domestic_rule.minimum,
            target=domestic_target,
            maximum=domestic_rule.maximum,
        ),
        RegionSelectionRule(
            region=international_rule.region,
            minimum=international_rule.minimum,
            target=international_target,
            maximum=international_rule.maximum,
        ),
    )


def fetch_region_pool(db: Session, region: str, cutoff: datetime, limit: int) -> list[NewsItem]:
    if limit <= 0:
        return []
    return list(
        db.scalars(
            select(NewsItem)
            .where(
                NewsItem.selected.is_(True),
                NewsItem.region == region,
                NewsItem.published_at >= cutoff,
            )
            .order_by(NewsItem.importance_score.desc(), NewsItem.published_at.desc())
            .limit(limit)
        )
    )


def fill_selection(
    selected_domestic: list[NewsItem],
    selected_international: list[NewsItem],
    domestic_pool: list[NewsItem],
    international_pool: list[NewsItem],
    domestic_rule: RegionSelectionRule,
    international_rule: RegionSelectionRule,
    article_limit: int,
) -> tuple[list[NewsItem], list[NewsItem]]:
    selected_ids = {item.id for item in [*selected_domestic, *selected_international]}
    domestic_remaining = [item for item in domestic_pool if item.id not in selected_ids]
    international_remaining = [item for item in international_pool if item.id not in selected_ids]

    while len(selected_domestic) + len(selected_international) < article_limit:
        added = False
        if len(selected_domestic) < domestic_rule.maximum and domestic_remaining:
            selected_domestic.append(domestic_remaining.pop(0))
            added = True
        if len(selected_domestic) + len(selected_international) >= article_limit:
            break
        if len(selected_international) < international_rule.maximum and international_remaining:
            selected_international.append(international_remaining.pop(0))
            added = True
        if not added:
            break

    return selected_domestic, selected_international
