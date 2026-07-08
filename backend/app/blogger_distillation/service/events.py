from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import OperationTask, OperationTaskEvent, TaskStatus

logger = logging.getLogger(__name__)


def note_title_label(title: str, n: int = 16) -> str:
    """采集进度文案用的短标题《…》;空标题返回空串(调用方退回通用文案)。"""
    text = (title or "").strip().replace("\n", " ")
    if not text:
        return ""
    return f"《{text[:n]}…》" if len(text) > n else f"《{text}》"


class DistillationCancelled(Exception):
    pass


def is_control_flow_exception(exc: BaseException) -> bool:
    """是否为"应放行、不该被业务 except 吞掉"的控制流异常:任务取消 / RQ 作业超时。

    子步骤(视觉、ASR)的 `except Exception` 若把这些也当"单条失败"吞掉,任务会带病续跑成孤儿,
    最终静默、被 20 分钟看门狗误判(见 #20)。这些异常必须一路上抛,让任务干净失败。
    """
    if isinstance(exc, DistillationCancelled):
        return True
    try:
        from rq.timeouts import JobTimeoutException
    except ImportError:
        return False
    return isinstance(exc, JobTimeoutException)


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
