from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import OperationTask, OperationTaskEvent, TaskStatus

logger = logging.getLogger(__name__)


class DistillationCancelled(Exception):
    pass


def record_task_event(
    db: Session,
    tenant_id: int,
    task_id: str,
    step_name: str,
    status: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    safe_message = truncate_task_event_message(message)
    logger.info("博主蒸馏事件：任务ID=%s，步骤=%s，状态=%s，%s", task_id, step_name, status, safe_message)
    try:
        db.add(
            OperationTaskEvent(
                tenant_id=tenant_id,
                task_id=task_id,
                step_name=step_name,
                status=status,
                message=safe_message,
                payload_json=json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("记录博主蒸馏事件失败：任务ID=%s，步骤=%s，状态=%s", task_id, step_name, status)


def truncate_task_event_message(message: str, limit: int = 480) -> str:
    normalized = " ".join(str(message).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def ensure_distillation_not_cancelled(db: Session, tenant_id: int, task_id: str) -> None:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant_id:
        return
    db.refresh(task)
    if task.status in {TaskStatus.cancel_requested, TaskStatus.cancelled}:
        message = "用户已请求停止流程，流程安全退出；已采集样本会保留，未发布新的 Skill"
        record_task_event(db, tenant_id, task_id, "停止蒸馏", "cancelled", message)
        raise DistillationCancelled(message)
