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

    另:仅压 root 级别不够——实测启动期 ``[app.*]`` INFO 可见,一旦进入请求处理,root 级别会被
    (uvicorn/某三方库在运行时)复位回 WARNING,于是应用层 INFO 全被吞、只剩 WARNING+(这正是当年
    超时观测被静默丢弃的同类坑)。所以显式把 ``app`` 这一祖先 logger 钉在 INFO:``app.*`` 的有效级别
    从此只认这里,不再随 root 被复位而变。root 的 handler 仍在(WARNING 能打出即证),INFO 过了级别
    检查就能落到该 handler。
    """
    for log_level, name in _LEVEL_NAMES_ZH.items():
        logging.addLevelName(log_level, name)
    logging.basicConfig(level=level, format=_LOG_FORMAT, force=True)
    logging.getLogger().setLevel(level)
    logging.getLogger("app").setLevel(level)  # 钉住应用日志子树,免疫 root 级别被运行时复位
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, HealthAccessLogFilter) for f in access.filters):
        access.addFilter(HealthAccessLogFilter())
