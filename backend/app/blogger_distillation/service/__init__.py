"""Blogger collection & distillation service, split by responsibility.

Re-exported here so existing ``from app.blogger_distillation.service import X``
imports keep working.
"""

from app.blogger_distillation.service.collection import (
    CollectionResult,
    build_collection_client,
    collect_posts,
    platform_collection_label,
    refresh_blogger_profile,
    run_blogger_collection,
    run_blogger_url_collection,
)
from app.blogger_distillation.service.crud import (
    archive_active_skills,
    create_blogger,
    delete_blogger,
    set_blogger_favorite,
    update_blogger,
)
from app.blogger_distillation.service.distillation import (
    DistillationResult,
    abandon_blogger_distillation,
    confirm_blogger_distillation,
    distill_with_llm,
    run_blogger_distillation,
)
from app.blogger_distillation.service.extract import (
    collect_video_url_candidates,
    extract_video_url,
    is_likely_video_url,
)
from app.blogger_distillation.service.events import (
    DistillationCancelled,
    ensure_distillation_not_cancelled,
    record_task_event,
    truncate_task_event_message,
)
from app.blogger_distillation.service.usage import apply_usage

__all__ = [
    "CollectionResult",
    "DistillationResult",
    "DistillationCancelled",
    "record_task_event",
    "truncate_task_event_message",
    "ensure_distillation_not_cancelled",
    "apply_usage",
    "archive_active_skills",
    "create_blogger",
    "update_blogger",
    "set_blogger_favorite",
    "delete_blogger",
    "run_blogger_collection",
    "run_blogger_url_collection",
    "refresh_blogger_profile",
    "build_collection_client",
    "collect_posts",
    "platform_collection_label",
    "run_blogger_distillation",
    "confirm_blogger_distillation",
    "abandon_blogger_distillation",
    "distill_with_llm",
    "extract_video_url",
    "is_likely_video_url",
    "collect_video_url_candidates",
]
