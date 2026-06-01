from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import BloggerPost


@dataclass
class PostQuality:
    level: str
    missing: list[str]
    has_content: bool
    has_interact: bool
    has_time: bool
    has_comments: bool


def evaluate_post_quality(data: dict[str, Any]) -> PostQuality:
    missing: list[str] = []
    has_content = bool(str(data.get("title") or "").strip() or str(data.get("body_text") or "").strip())
    has_interact = any(int(data.get(key) or 0) > 0 for key in ("like_count", "favorite_count", "comment_count", "share_count"))
    has_time = data.get("published_at") is not None
    comments_json = str(data.get("comments_json") or "[]")
    has_comments = comments_json not in ("", "[]")
    if not has_content:
        return PostQuality("failed", ["content"], False, has_interact, has_time, has_comments)
    if not has_interact:
        missing.append("interact")
    if not has_time:
        missing.append("time")
    if not has_comments:
        missing.append("comments")
    return PostQuality("complete" if not missing else "partial", missing, has_content, has_interact, has_time, has_comments)


def quality_report(posts: list[BloggerPost], requested_count: int) -> dict[str, Any]:
    total = len(posts)
    with_content = sum(1 for item in posts if item.title.strip() or item.body_text.strip())
    with_time = sum(1 for item in posts if item.published_at is not None)
    with_comments = sum(1 for item in posts if item.comments_json not in ("", "[]"))
    unique_ids = len({item.external_id for item in posts})
    content_ratio = round(with_content / max(total, 1), 4)
    requested_ratio = round(total / max(requested_count, 1), 4)
    warnings: list[str] = []
    if total < requested_count * 0.7:
        warnings.append(f"样本数量不足：目标 {requested_count} 条，实际 {total} 条")
    if content_ratio < 0.5:
        warnings.append("正文完整率低于 50%，本次蒸馏质量可能不足")
    if unique_ids < total:
        warnings.append(f"存在重复笔记 ID：重复 {total - unique_ids} 条")
    return {
        "requested_count": requested_count,
        "sample_count": total,
        "requested_ratio": requested_ratio,
        "content_count": with_content,
        "content_ratio": content_ratio,
        "time_count": with_time,
        "time_ratio": round(with_time / max(total, 1), 4),
        "comment_covered_count": with_comments,
        "comment_coverage": round(with_comments / max(total, 1), 4),
        "duplicate_count": total - unique_ids,
        "warnings": warnings,
    }
