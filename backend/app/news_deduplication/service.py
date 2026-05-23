import logging
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import NewsItem
from app.news_deduplication.models import DeduplicationReport, DuplicateDecision
from app.news_deduplication.prompts import build_duplicate_review_prompt
from app.news_deduplication.validators import validate_duplicate_review
from app.services.ai_service import AIServiceError, create_json_response, is_ai_enabled


logger = logging.getLogger(__name__)


def deduplicate_processed_news(
    db: Session,
    settings: Settings,
    tenant_id: int,
    processed_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], DeduplicationReport]:
    lookback_days = max(1, settings.dedup_lookback_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    recent_items = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.tenant_id == tenant_id, NewsItem.published_at >= cutoff)
            .order_by(NewsItem.published_at.desc())
        )
    )
    logger.info(
        "新闻去重开始：租户ID=%s，候选=%s，历史窗口=%s天，历史新闻=%s",
        tenant_id,
        len(processed_items),
        lookback_days,
        len(recent_items),
    )

    unique_items: list[dict[str, Any]] = []
    accepted_snapshots: list[dict[str, Any]] = []
    direct_duplicate_count = 0
    llm_duplicate_count = 0
    review_count = 0
    duplicate_details: list[dict[str, Any]] = []

    for item in processed_items:
        item["_dedup_key"] = build_dedup_key(item)
        decision = find_duplicate(db, settings, item, recent_items, accepted_snapshots)
        if decision.method == "llm_review":
            review_count += 1
        if decision.is_duplicate:
            if decision.method == "llm_review":
                llm_duplicate_count += 1
            else:
                direct_duplicate_count += 1
            duplicate_details.append(
                {
                    "标题": str(item.get("title") or "")[:120],
                    "重复新闻ID": decision.duplicate_of_id,
                    "相似度": round(decision.similarity, 3),
                    "方式": decision.method,
                    "原因": decision.reason,
                }
            )
            logger.info(
                "新闻去重跳过重复：标题=%s，重复新闻ID=%s，相似度=%.3f，方式=%s，原因=%s",
                truncate_log_text(str(item.get("title") or "")),
                decision.duplicate_of_id,
                decision.similarity,
                method_label(decision.method),
                decision.reason,
            )
            continue
        unique_items.append(item)
        accepted_snapshots.append(item)

    report = DeduplicationReport(
        input_count=len(processed_items),
        unique_count=len(unique_items),
        duplicate_count=len(processed_items) - len(unique_items),
        direct_duplicate_count=direct_duplicate_count,
        llm_duplicate_count=llm_duplicate_count,
        review_count=review_count,
        duplicates=duplicate_details,
    )
    logger.info(
        "新闻去重完成：输入=%s，保留=%s，重复=%s，直接判重=%s，大模型判重=%s，大模型复核=%s",
        report.input_count,
        report.unique_count,
        report.duplicate_count,
        report.direct_duplicate_count,
        report.llm_duplicate_count,
        report.review_count,
    )
    return unique_items, report


def find_duplicate(
    db: Session,
    settings: Settings,
    item: dict[str, Any],
    recent_items: list[NewsItem],
    accepted_snapshots: list[dict[str, Any]],
) -> DuplicateDecision:
    item_key = str(item.get("_dedup_key") or "")
    item_url = normalize_urlish(str(item.get("url") or ""))
    item_title_key = normalize_title_key(str(item.get("title") or ""))

    for existing in recent_items:
        if item_url and normalize_urlish(existing.url) == item_url:
            return DuplicateDecision(True, existing.id, "URL 完全相同", 1.0, "url")
        if item_title_key and normalize_title_key(existing.title) == item_title_key:
            return DuplicateDecision(True, existing.id, "标题规范化后完全相同", 1.0, "title")
        if item_key and existing.dedup_key and existing.dedup_key == item_key:
            return DuplicateDecision(True, existing.id, "去重键完全相同", 1.0, "dedup_key")

    snapshot_candidates = [
        item_to_candidate(existing)
        for existing in recent_items
    ] + [
        snapshot_to_candidate(snapshot, index)
        for index, snapshot in enumerate(accepted_snapshots, start=1)
    ]
    best_candidate, best_similarity = most_similar_candidate(item, snapshot_candidates)
    if not best_candidate:
        return DuplicateDecision(False, None, "没有相似历史新闻", 0.0, "none")

    if best_similarity >= settings.dedup_direct_similarity:
        return DuplicateDecision(
            True,
            best_candidate.get("id"),
            "轻量向量相似度超过直接判重阈值",
            best_similarity,
            "vector_direct",
        )

    if best_similarity < settings.dedup_review_similarity:
        return DuplicateDecision(False, None, "相似度低于复核阈值", best_similarity, "vector")

    if not settings.dedup_enable_llm_review or not is_ai_enabled(settings):
        return DuplicateDecision(False, None, "相似度需要复核，但大模型复核未启用", best_similarity, "vector")

    try:
        data = create_json_response(
            settings=settings,
            prompt=build_duplicate_review_prompt(
                candidate=dedup_prompt_payload(item),
                existing=best_candidate,
                similarity=best_similarity,
            ),
        )
        is_duplicate, reason = validate_duplicate_review(data)
    except AIServiceError as exc:
        logger.warning("新闻去重大模型复核失败：错误=%s", exc)
        return DuplicateDecision(False, None, "大模型复核失败，保留候选新闻", best_similarity, "llm_review_failed")

    return DuplicateDecision(
        is_duplicate=is_duplicate,
        duplicate_of_id=best_candidate.get("id") if is_duplicate else None,
        reason=reason,
        similarity=best_similarity,
        method="llm_review",
    )


def most_similar_candidate(
    item: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float]:
    item_vector = text_vector(dedup_text(item))
    best_candidate: dict[str, Any] | None = None
    best_similarity = 0.0
    for candidate in candidates:
        similarity = cosine_similarity(item_vector, text_vector(dedup_text(candidate)))
        if similarity > best_similarity:
            best_similarity = similarity
            best_candidate = candidate
    return best_candidate, best_similarity


def item_to_candidate(item: NewsItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "summary": item.summary,
        "category": item.category,
        "source": item.source,
        "url": item.url,
        "published_at": item.published_at.isoformat(),
        "region": item.region,
    }


def snapshot_to_candidate(item: dict[str, Any], index: int) -> dict[str, Any]:
    payload = dedup_prompt_payload(item)
    payload["id"] = None
    payload["batch_index"] = index
    return payload


def dedup_prompt_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": item.get("title"),
        "summary": item.get("summary"),
        "category": item.get("category"),
        "source": item.get("source"),
        "url": item.get("url"),
        "published_at": item.get("published_at"),
        "region": item.get("region"),
    }


def build_dedup_key(item: dict[str, Any]) -> str:
    title = normalize_title_key(str(item.get("title") or ""))
    category = normalize_title_key(str(item.get("category") or ""))
    return f"{title[:140]}::{category[:40]}"[:200]


def dedup_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "category", "source", "region")
    )


def text_vector(text: str) -> Counter[str]:
    normalized = normalize_text(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    cjk_bigrams = ["".join(cjk_chars[index : index + 2]) for index in range(max(0, len(cjk_chars) - 1))]
    cjk_trigrams = ["".join(cjk_chars[index : index + 3]) for index in range(max(0, len(cjk_chars) - 2))]
    return Counter(tokens + cjk_chars + cjk_bigrams + cjk_trigrams)


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def normalize_title_key(value: str) -> str:
    return normalize_text(value).replace(" ", "")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_urlish(value: str) -> str:
    return value.strip().rstrip("/").lower()


def truncate_log_text(value: str, limit: int = 80) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else f"{text[:limit]}..."


def method_label(method: str) -> str:
    return {
        "url": "URL",
        "title": "标题",
        "dedup_key": "去重键",
        "vector_direct": "轻量向量",
        "llm_review": "大模型复核",
        "llm_review_failed": "大模型复核失败",
        "vector": "轻量向量",
    }.get(method, method)
