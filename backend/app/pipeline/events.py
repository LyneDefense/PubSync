import json
import logging
from typing import Any

from app.pipeline.context import PipelineContext
from app.models import OperationTaskEvent


logger = logging.getLogger(__name__)


def record_event(
    context: PipelineContext,
    step_name: str,
    status: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    safe_message = truncate_event_message(message)
    logger.info("流程事件：任务ID=%s，步骤=%s，状态=%s，%s", context.task_id, step_name, status_label(status), safe_message)
    try:
        context.db.add(
            OperationTaskEvent(
                task_id=context.task_id,
                tenant_id=context.tenant.id,
                step_name=step_name,
                status=status,
                message=safe_message,
                payload_json=json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
            )
        )
        context.db.commit()
    except Exception:
        context.db.rollback()
        logger.exception("记录流程事件失败：任务ID=%s，步骤=%s，状态=%s", context.task_id, step_name, status)


def truncate_event_message(message: str, limit: int = 480) -> str:
    normalized = " ".join(str(message).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def status_label(status: str) -> str:
    return {
        "queued": "排队中",
        "running": "进行中",
        "succeeded": "已完成",
        "failed": "失败",
    }.get(status, status)
