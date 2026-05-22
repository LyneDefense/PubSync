from typing import Any

from app.news_fetching.models import RawNewsCandidate
from app.news_processing.models import ProcessedNewsItem


ALLOWED_CATEGORIES = {
    "模型发布",
    "研究进展",
    "企业应用",
    "开源项目",
    "基础设施",
    "开发者工具",
    "产品更新",
    "政策监管",
    "资本市场",
    "行业观察",
}


def validate_processed_items(raw_items: object, candidates: list[RawNewsCandidate]) -> list[ProcessedNewsItem]:
    if not isinstance(raw_items, list):
        return []

    candidate_map = {candidate.candidate_id: candidate for candidate in candidates}
    used_candidate_ids: set[str] = set()
    processed: list[ProcessedNewsItem] = []

    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        candidate_id = str(raw_item.get("candidate_id") or "").strip()
        if not candidate_id or candidate_id in used_candidate_ids or candidate_id not in candidate_map:
            continue

        score = normalize_score(raw_item.get("importance_score"))
        if score is None or score < 70:
            continue

        candidate = candidate_map[candidate_id]
        used_candidate_ids.add(candidate_id)
        duplicate_candidate_ids = normalize_duplicate_ids(raw_item.get("duplicate_candidate_ids"), candidate_map, used_candidate_ids)
        used_candidate_ids.update(duplicate_candidate_ids)
        processed.append(
            ProcessedNewsItem(
                candidate=candidate,
                display_title=normalize_text(raw_item.get("display_title"), candidate.title)[:500],
                summary=normalize_text(raw_item.get("summary"), candidate.summary or "暂无摘要"),
                category=normalize_category(raw_item.get("category")),
                importance_score=score,
                importance_reason=normalize_text(raw_item.get("importance_reason"), ""),
                key_facts=normalize_string_list(raw_item.get("key_facts"))[:5],
                duplicate_candidate_ids=duplicate_candidate_ids,
            )
        )

    return sorted(processed, key=lambda item: item.importance_score, reverse=True)


def normalize_duplicate_ids(value: Any, candidate_map: dict[str, RawNewsCandidate], used_candidate_ids: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    duplicate_ids: list[str] = []
    for item in value:
        candidate_id = str(item).strip()
        if candidate_id in candidate_map and candidate_id not in used_candidate_ids and candidate_id not in duplicate_ids:
            duplicate_ids.append(candidate_id)
    return duplicate_ids


def normalize_score(value: object) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, score))


def normalize_category(value: object) -> str:
    category = normalize_text(value, "")
    if category in ALLOWED_CATEGORIES:
        return category
    return "行业观察"


def normalize_text(value: object, default: str) -> str:
    if isinstance(value, list):
        value = "；".join(str(item) for item in value if item)
    if not isinstance(value, str):
        return default
    text = " ".join(value.strip().split())
    return text or default


def normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(item, "") for item in value if normalize_text(item, "")]
