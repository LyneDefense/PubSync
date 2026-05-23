import json
import logging
from typing import Any

from app.harness.context import HarnessContext
from app.models import OperationTaskEvent


logger = logging.getLogger(__name__)


def record_event(
    context: HarnessContext,
    step_name: str,
    status: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    logger.info("流程事件：任务ID=%s，步骤=%s，状态=%s，%s", context.task_id, step_name, status_label(status), message)
    context.db.add(
        OperationTaskEvent(
            task_id=context.task_id,
            step_name=step_name,
            status=status,
            message=message,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
        )
    )
    context.db.commit()


def status_label(status: str) -> str:
    return {
        "queued": "排队中",
        "running": "进行中",
        "succeeded": "已完成",
        "failed": "失败",
    }.get(status, status)
