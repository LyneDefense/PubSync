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


class HealthAccessLogFilter(logging.Filter):
    """Drop uvicorn access-log lines for ``/health`` to keep the log readable."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            return str(args[2]).split("?", 1)[0] != "/health"
        return "/health" not in record.getMessage()


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging, Chinese level names and the /health access filter.

    安全可重复调用。关键点:``force=True``——uvicorn 用纯 ``uvicorn app.main:app`` 起服务时,
    它自己的日志初始化会先在 root 上挂 handler,导致普通 ``basicConfig`` 变成空操作、应用层
    ``logger.info`` 全被吞掉(只剩 uvicorn 的访问日志)。force 会清掉 root 上已有的 handler 再装我们
    的,并显式把 root level 压到 INFO,保证 ``[app.*]`` 的 INFO 能打到 stdout。uvicorn.access /
    uvicorn.error 有自己的 handler(propagate=False),不受 root 重置影响。

    main.py 在 import 期与 lifespan 启动期各调一次:后者发生在 uvicorn 日志初始化「之后」,
    确保我们的配置最终生效(谁后调谁赢)。
    """
    for log_level, name in _LEVEL_NAMES_ZH.items():
        logging.addLevelName(log_level, name)
    logging.basicConfig(level=level, format=_LOG_FORMAT, force=True)
    logging.getLogger().setLevel(level)
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, HealthAccessLogFilter) for f in access.filters):
        access.addFilter(HealthAccessLogFilter())
