from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant
from app.database import get_db
from app.models import OperationTask, OperationTaskEvent, Tenant
from app.schemas import OperationTaskEventRead, OperationTaskRead
from app.services.task_service import request_task_cancel

router = APIRouter()


@router.get("/tasks/{task_id}", response_model=OperationTaskRead)
def get_task_endpoint(task_id: str, tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=OperationTaskRead)
def cancel_task_endpoint(task_id: str, tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type != "blogger_distillation":
        raise HTTPException(status_code=400, detail="Only blogger distillation tasks can be stopped")
    request_task_cancel(db, task)
    db.refresh(task)
    return task


@router.get("/tasks/{task_id}/events", response_model=list[OperationTaskEventRead])
def list_task_events_endpoint(
    task_id: str,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[OperationTaskEvent]:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Task not found")
    stmt = (
        select(OperationTaskEvent)
        .where(OperationTaskEvent.task_id == task_id, OperationTaskEvent.tenant_id == tenant.id)
        .order_by(OperationTaskEvent.created_at.asc(), OperationTaskEvent.id.asc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))
