"""后台任务队列管理 API:跨租户查看任务/事件、取消、重试,以及队列健康。"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, require_admin
from app.database import get_db
from app.models import OperationTask, OperationTaskEvent, TaskStatus
from app.queue import submit_background
from app.schemas import AdminTaskRead, OperationTaskEventRead, QueueHealth
from app.services.task_service import (
    request_task_cancel,
    run_article_generation_task,
    run_daily_publish_task,
    run_news_fetch_task,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 只接受 task_id 单参数、可一键重试的任务类型。带参任务(采集/蒸馏/发布包/体检)
# 的原始入参未持久化,无法凭任务记录重放,故不在此列。
RETRYABLE = {
    "news_fetch": run_news_fetch_task,
    "article_generation": run_article_generation_task,
    "daily_publish": run_daily_publish_task,
}

TERMINAL = {TaskStatus.succeeded, TaskStatus.failed, TaskStatus.cancelled}


@router.get("/admin/tasks", response_model=list[AdminTaskRead])
def admin_list_tasks_endpoint(
    status: str | None = Query(default=None, description="按状态筛选"),
    task_type: str | None = Query(default=None, description="按类型筛选"),
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[OperationTask]:
    stmt = select(OperationTask)
    if status:
        stmt = stmt.where(OperationTask.status == status)
    if task_type:
        stmt = stmt.where(OperationTask.task_type == task_type)
    stmt = stmt.order_by(OperationTask.created_at.desc())
    # 默认给个上限,避免一次拉全表。
    effective_limit = limit if limit is not None else 100
    return list(db.scalars(apply_pagination(stmt, effective_limit, offset)))


@router.get("/admin/tasks/{task_id}/events", response_model=list[OperationTaskEventRead])
def admin_task_events_endpoint(
    task_id: str,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[OperationTaskEvent]:
    if not db.get(OperationTask, task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    stmt = (
        select(OperationTaskEvent)
        .where(OperationTaskEvent.task_id == task_id)
        .order_by(OperationTaskEvent.created_at.asc(), OperationTaskEvent.id.asc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.post("/admin/tasks/{task_id}/cancel", response_model=AdminTaskRead)
def admin_cancel_task_endpoint(
    task_id: str,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    # 置「请求取消」标记;支持协作式取消的任务(采集/蒸馏)会在当前步骤后安全退出。
    request_task_cancel(db, task)
    db.refresh(task)
    return task


@router.post("/admin/tasks/{task_id}/retry", response_model=AdminTaskRead)
def admin_retry_task_endpoint(
    task_id: str,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in TERMINAL:
        raise HTTPException(status_code=400, detail="任务尚未结束，无需重试")
    runner = RETRYABLE.get(task.task_type)
    if runner is None:
        raise HTTPException(status_code=400, detail="该类型任务暂不支持一键重试（缺少原始参数）")
    task.status = TaskStatus.queued
    task.message = "已重新加入后台任务"
    task.error_message = None
    db.commit()
    db.refresh(task)
    submit_background(None, runner, task.id)
    return task


@router.get("/admin/queue", response_model=QueueHealth)
def admin_queue_health_endpoint(
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> QueueHealth:
    from app.config import get_settings

    settings = get_settings()
    if not settings.use_task_queue:
        return QueueHealth(use_task_queue=False, note="未启用持久化队列，任务在进程内执行")
    try:
        from app.queue import get_task_queue

        queue = get_task_queue()
        return QueueHealth(
            use_task_queue=True,
            queue_name=settings.task_queue_name,
            queued=queue.count,
            failed=queue.failed_job_registry.count,
        )
    except Exception as exc:  # noqa: BLE001 - Redis 不可达时给出可读提示而非 500
        logger.warning("读取队列健康失败：%s", exc)
        return QueueHealth(use_task_queue=True, queue_name=settings.task_queue_name, note=f"队列连接异常：{exc}")
