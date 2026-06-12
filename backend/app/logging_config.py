"""Centralized logging configuration.

Both entry points (the FastAPI app in ``app.main`` and the RQ worker in
``app.worker``) call :func:`configure_logging` so logs share one format, the same
Chinese level names, and the ``/health`` access-log filter — previously these were
configured inconsistently in two places.
"""

from __future__ import annotations

import logging

_LEVEL_NAMES_ZH = {
    logging.DEBUG: "调试",
    logging.INFO: "信息",
    logging.WARNING: "警告",
    logging.ERROR: "错误",
    logging.CRITICAL: "严重",
}

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

_configured = False


class HealthAccessLogFilter(logging.Filter):
    """Drop uvicorn access-log lines for ``/health`` to keep the log readable."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            return str(args[2]).split("?", 1)[0] != "/health"
        return "/health" not in record.getMessage()


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotently configure root logging, level names and the health filter."""
    global _configured
    if _configured:
        return
    for log_level, name in _LEVEL_NAMES_ZH.items():
        logging.addLevelName(log_level, name)
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    logging.getLogger("uvicorn.access").addFilter(HealthAccessLogFilter())
    _configured = True
