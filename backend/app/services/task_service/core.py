"""后台任务的生命周期原语:建任务、统一执行壳、状态流转(running/succeeded/cancelled/failed)。

所有 ``run_*_task`` 都走 :func:`execute_task` 这层壳——它统一处理开 session、查任务、
取消检查、成功/预期失败/意外异常的记账与 session 清理,任务本身只写 ``work`` 回调。
"""

import logging
from collections.abc import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.admin.runtime_config import apply_overrides
from app.blogger_distillation.service import DistillationCancelled
from app.config import get_settings
from app.cost.context import cost_capture
from app.database import SessionLocal
from app.models import OperationTask, TaskStatus

logger = logging.getLogger(__name__)

TASK_MESSAGES = {
    "news_fetch": "已加入后台抓取任务",
    "article_generation": "已加入后台生成任务",
    "daily_publish": "已加入定时发布任务",
    "blogger_collection": "已加入博主样本采集任务",
    "blogger_distillation": "已加入博主蒸馏任务",
    "xhs_package_draft": "已加入小红书发布包生成任务",
    "account_audit": "已加入账号体检任务",
}


def create_operation_task(db: Session, task_type: str, tenant_id: int, message: str | None = None) -> OperationTask:
    task = OperationTask(
        id=str(uuid4()),
        tenant_id=tenant_id,
        task_type=task_type,
        status=TaskStatus.queued,
        message=message or TASK_MESSAGES.get(task_type, "已加入后台任务"),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def execute_task(
    task_id: str,
    *,
    label: str,
    fail_message: str,
    work: Callable[[Session, OperationTask], None],
    expected: tuple[type[BaseException], ...] = (),
    cancellable: bool = False,
    on_unexpected: Callable[[Session, str, Exception], None] | None = None,
) -> None:
    """Shared lifecycle for background tasks.

    Handles the boilerplate every ``run_*_task`` previously duplicated: opening a
    session, looking up the task, an optional cancel check, and uniform
    success/expected-failure/unexpected-exception bookkeeping plus session cleanup.
    ``work`` performs the task-specific steps; ``expected`` exceptions are recorded
    as a normal failure, while anything else is logged at exception level and
    re-raised after being marked failed.
    """
    db = SessionLocal()
    try:
        logger.info("任务开始：任务ID=%s，类型=%s", task_id, label)
        # worker 进程在每个任务开跑前刷新一次后台运行时配置(模型/ASR/密钥等),
        # 这样管理员在后台改的配置无需重启 worker 即可生效。
        apply_overrides(get_settings(), db)
        task = get_task(db, task_id)
        if not task:
            return
        if cancellable and task.status == TaskStatus.cancel_requested:
            mark_task_cancelled(db, task, f"{label}已停止")
            return
        # 包裹任务执行:期间所有 TikHub/LLM 调用的费用归属到该 task/tenant,结束统一落库。
        with cost_capture(tenant_id=task.tenant_id, task_id=task_id):
            work(db, task)
    except DistillationCancelled as exc:
        logger.info("任务停止：任务ID=%s，类型=%s，原因=%s", task_id, label, exc)
        mark_task_cancelled_by_id(db, task_id, f"{label}已停止", str(exc))
    except expected as exc:
        logger.warning("任务失败：任务ID=%s，类型=%s，错误=%s", task_id, label, exc)
        mark_task_failed_by_id(db, task_id, fail_message, str(exc))
    except Exception as exc:
        logger.exception("任务异常：任务ID=%s，类型=%s", task_id, label)
        if on_unexpected is not None:
            try:
                on_unexpected(db, task_id, exc)
            except Exception:
                logger.exception("记录任务失败事件失败：任务ID=%s", task_id)
        mark_task_failed_by_id(db, task_id, fail_message, f"{type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


def get_task(db: Session, task_id: str) -> OperationTask | None:
    return db.get(OperationTask, task_id)


def mark_task_running(db: Session, task: OperationTask, message: str) -> None:
    task.status = TaskStatus.running
    task.message = message
    task.error_message = None
    db.commit()


def mark_task_succeeded(db: Session, task: OperationTask, message: str, article_id: int | None = None) -> None:
    task.status = TaskStatus.succeeded
    task.message = message
    task.article_id = article_id
    task.error_message = None
    db.commit()


def request_task_cancel(db: Session, task: OperationTask) -> None:
    if task.status in {TaskStatus.succeeded, TaskStatus.failed, TaskStatus.cancelled}:
        return
    task.status = TaskStatus.cancel_requested
    task.message = "正在请求停止任务，当前步骤结束后会安全退出"
    db.commit()


def mark_task_cancelled(db: Session, task: OperationTask, message: str, error_message: str | None = None) -> None:
    task.status = TaskStatus.cancelled
    task.message = message
    task.error_message = error_message
    db.commit()


def mark_task_cancelled_by_id(db: Session, task_id: str, message: str, error_message: str | None = None) -> None:
    db.rollback()
    task = get_task(db, task_id)
    if not task:
        return
    mark_task_cancelled(db, task, message, error_message)


def mark_task_failed_by_id(db: Session, task_id: str, message: str, error_message: str) -> None:
    db.rollback()
    task = get_task(db, task_id)
    if not task:
        return
    task.status = TaskStatus.failed
    task.message = message
    task.error_message = error_message
    db.commit()
