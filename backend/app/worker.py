"""RQ worker entry point.

Run with ``python -m app.worker``. Consumes the PubSync task queue and executes
the same ``run_*_task`` functions the API enqueues. Requires ``USE_TASK_QUEUE=true``
and a reachable ``REDIS_URL``; the database schema is ensured on startup so a
freshly started worker can run before the API has booted.
"""

from __future__ import annotations

import logging

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings
from app.database import create_db_and_tables
from app.logging_config import configure_logging


logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    settings = get_settings()
    create_db_and_tables()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.task_queue_name, connection=connection)
    logger.info("PubSync worker 启动：queue=%s，redis=%s", settings.task_queue_name, settings.redis_url)
    Worker([queue], connection=connection).work(with_scheduler=True)


if __name__ == "__main__":
    main()
