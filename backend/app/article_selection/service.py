import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.article_selection.models import ArticleSelectionResult, GroupSelectionRule
from app.config import Settings
from app.models import ContentGroup, ContentProfile, NewsItem


logger = logging.getLogger(__name__)


def select_article_news(
    db: Session,
    settings: Settings,
    tenant_id: int,
    profile: ContentProfile | None = None,
    content_groups: list[ContentGroup] | None = None,
) -> ArticleSelectionResult:
    article_limit = max(1, settings.article_news_limit)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, settings.article_news_lookback_hours))
    groups = [group for group in (content_groups or []) if group.enabled]
    if not groups or (profile and profile.grouping_mode == "none"):
        return select_article_news_without_groups(db, tenant_id, cutoff, article_limit)

    rules = fit_targets_to_limit(
        [build_rule(group, article_limit) for group in groups],
        article_limit,
    )
    pools = {rule.group_key: fetch_group_pool(db, tenant_id, rule.group_key, cutoff, rule.maximum) for rule in rules}
    selected_by_group = {rule.group_key: pools[rule.group_key][: rule.target] for rule in rules}

    logger.info(
        "文章新闻候选池准备完成：%s",
        "，".join(f"{rule.group_name}={len(pools[rule.group_key])}" for rule in rules),
    )
    fill_selection(selected_by_group, pools, rules, article_limit)
    ordered_items = flatten_selection(selected_by_group, rules)[:article_limit]
    group_counts = {rule.group_name: len(selected_by_group[rule.group_key]) for rule in rules}
    logger.info(
        "文章新闻选择完成：总数=%s，分组=%s，可用候选=%s",
        len(ordered_items),
        group_counts,
        sum(len(pool) for pool in pools.values()),
    )
    return ArticleSelectionResult(
        news_items=ordered_items,
        group_counts=group_counts,
        total_available=sum(len(pool) for pool in pools.values()),
    )


def build_rule(group: ContentGroup, article_limit: int) -> GroupSelectionRule:
    return GroupSelectionRule(
        group_key=group.group_key,
        group_name=group.name,
        minimum=group.article_min,
        target=group.article_target,
        maximum=group.article_max,
        position=group.position,
    ).normalized(article_limit)


def select_article_news_without_groups(
    db: Session,
    tenant_id: int,
    cutoff: datetime,
    article_limit: int,
) -> ArticleSelectionResult:
    pool = list(
        db.scalars(
            base_news_query(tenant_id, cutoff)
            .order_by(NewsItem.importance_score.desc(), NewsItem.published_at.desc())
            .limit(article_limit)
        )
    )
    logger.info("文章新闻选择完成：不分组，总数=%s，可用候选=%s", len(pool), len(pool))
    return ArticleSelectionResult(news_items=pool, group_counts={"精选内容": len(pool)}, total_available=len(pool))


def fit_targets_to_limit(rules: list[GroupSelectionRule], article_limit: int) -> list[GroupSelectionRule]:
    ordered = sorted(rules, key=lambda rule: rule.position)
    minimum_total = sum(rule.minimum for rule in ordered)
    if minimum_total > article_limit:
        return trim_minimums(ordered, article_limit)
    target_total = sum(rule.target for rule in ordered)
    if target_total <= article_limit:
        return ordered
    overflow = target_total - article_limit
    fitted: list[GroupSelectionRule] = []
    for rule in reversed(ordered):
        reducible = max(0, rule.target - rule.minimum)
        reduction = min(reducible, overflow)
        overflow -= reduction
        fitted.append(
            GroupSelectionRule(
                group_key=rule.group_key,
                group_name=rule.group_name,
                minimum=rule.minimum,
                target=rule.target - reduction,
                maximum=rule.maximum,
                position=rule.position,
            )
        )
    return sorted(reversed(fitted), key=lambda rule: rule.position)


def trim_minimums(rules: list[GroupSelectionRule], article_limit: int) -> list[GroupSelectionRule]:
    remaining = article_limit
    fitted: list[GroupSelectionRule] = []
    for rule in rules:
        target = min(rule.minimum, remaining)
        remaining -= target
        fitted.append(
            GroupSelectionRule(
                group_key=rule.group_key,
                group_name=rule.group_name,
                minimum=target,
                target=target,
                maximum=max(target, rule.maximum),
                position=rule.position,
            )
        )
    return fitted


def base_news_query(tenant_id: int, cutoff: datetime):
    return select(NewsItem).where(
        NewsItem.selected.is_(True),
        NewsItem.tenant_id == tenant_id,
        NewsItem.published_at >= cutoff,
        or_(NewsItem.dedup_status.is_(None), NewsItem.dedup_status == "unique"),
    )


def fetch_group_pool(db: Session, tenant_id: int, group_key: str, cutoff: datetime, limit: int) -> list[NewsItem]:
    if limit <= 0:
        return []
    return list(
        db.scalars(
            base_news_query(tenant_id, cutoff)
            .where(NewsItem.group_key == group_key)
            .order_by(NewsItem.importance_score.desc(), NewsItem.published_at.desc())
            .limit(limit)
        )
    )


def fill_selection(
    selected_by_group: dict[str, list[NewsItem]],
    pools: dict[str, list[NewsItem]],
    rules: list[GroupSelectionRule],
    article_limit: int,
) -> None:
    selected_ids = {item.id for items in selected_by_group.values() for item in items}
    while sum(len(items) for items in selected_by_group.values()) < article_limit:
        best_rule: GroupSelectionRule | None = None
        best_item: NewsItem | None = None
        for rule in rules:
            if len(selected_by_group[rule.group_key]) >= rule.maximum:
                continue
            for item in pools[rule.group_key]:
                if item.id not in selected_ids:
                    if best_item is None or (item.importance_score, item.published_at) > (
                        best_item.importance_score,
                        best_item.published_at,
                    ):
                        best_item = item
                        best_rule = rule
                    break
        if best_rule is None or best_item is None:
            break
        selected_by_group[best_rule.group_key].append(best_item)
        selected_ids.add(best_item.id)


def flatten_selection(selected_by_group: dict[str, list[NewsItem]], rules: list[GroupSelectionRule]) -> list[NewsItem]:
    news_items: list[NewsItem] = []
    for rule in rules:
        news_items.extend(selected_by_group[rule.group_key])
    return news_items
