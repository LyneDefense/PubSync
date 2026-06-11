"""Optional persistent task queue (RQ + Redis).

PubSync historically ran long tasks (news fetch, article generation, blogger
collection/distillation) via FastAPI ``BackgroundTasks``. Those run in-process and
are lost on restart. This module adds an opt-in Redis-backed queue so tasks
survive restarts and run in dedicated worker processes.

Behaviour is controlled by ``USE_TASK_QUEUE`` (default false):

* ``False`` — :func:`submit_background` falls back to ``BackgroundTasks`` and the
  app behaves exactly as before. No Redis or worker is required.
* ``True``  — tasks are enqueued to Redis and executed by ``python -m app.worker``.

``redis`` / ``rq`` are imported lazily so the default in-process path keeps working
even if a Redis connection is unavailable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from app.config import get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import BackgroundTasks
    from rq import Queue


logger = logging.getLogger(__name__)

_queue: "Queue | None" = None


def get_task_queue() -> "Queue":
    """Return the process-wide RQ queue, creating it (and the Redis connection) lazily."""
    global _queue
    if _queue is None:
        from redis import Redis
        from rq import Queue

        settings = get_settings()
        _queue = Queue(
            settings.task_queue_name,
            connection=Redis.from_url(settings.redis_url),
            default_timeout=settings.task_job_timeout_seconds,
        )
    return _queue


def enqueue(func: Callable[..., Any], *args: Any) -> None:
    """Enqueue ``func(*args)`` onto the Redis queue for a worker to execute."""
    get_task_queue().enqueue(func, *args)


def submit_background(background_tasks: "BackgroundTasks | None", func: Callable[..., Any], *args: Any) -> None:
    """Dispatch a background task via the queue when enabled, else in-process.

    Falls back to in-process execution if enqueueing fails (e.g. Redis is down),
    so a misconfigured queue never silently drops user-triggered work.
    """
    settings = get_settings()
    if settings.use_task_queue:
        try:
            enqueue(func, *args)
            return
        except Exception:  # noqa: BLE001 - fall back to local execution on any queue error
            logger.exception("任务入队失败，回退到本地执行：func=%s", getattr(func, "__name__", func))
    if background_tasks is not None:
        background_tasks.add_task(func, *args)
    else:
        func(*args)
