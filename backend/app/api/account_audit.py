from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant
from app.database import get_db
from app.models import AccountAuditRun, BloggerProfile, Tenant
from app.queue import submit_background
from app.schemas import AccountAuditCreate, AccountAuditRunRead, OperationTaskRead, SelfDiagnoseCreate
from app.services.task_service import create_operation_task, run_account_audit_task

router = APIRouter()


def _require_account(db: Session, tenant_id: int, platform: str, blogger_id: int, label: str) -> BloggerProfile:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"{label}不存在")
    if blogger.platform != platform:
        raise HTTPException(status_code=400, detail=f"{label}与所选平台不一致")
    return blogger


@router.post("/account-audit", response_model=OperationTaskRead)
def start_account_audit_endpoint(
    payload: AccountAuditCreate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    _require_account(db, tenant.id, payload.platform, payload.my_blogger_id, "我的账号")
    _require_account(db, tenant.id, payload.platform, payload.benchmark_blogger_id, "对标账号")
    task = create_operation_task(db, "account_audit", tenant_id=tenant.id)
    submit_background(background_tasks, run_account_audit_task, task.id, {"kind": "benchmark", **payload.model_dump()})
    return task


@router.post("/account-audit/self", response_model=OperationTaskRead)
def start_self_diagnose_endpoint(
    payload: SelfDiagnoseCreate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    _require_account(db, tenant.id, payload.platform, payload.my_blogger_id, "我的账号")
    task = create_operation_task(db, "account_audit", tenant_id=tenant.id)
    submit_background(background_tasks, run_account_audit_task, task.id, {"kind": "self", **payload.model_dump()})
    return task


@router.get("/account-audit/runs", response_model=list[AccountAuditRunRead])
def list_account_audit_runs_endpoint(
    platform: str | None = None,
    kind: str | None = None,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[AccountAuditRun]:
    stmt = select(AccountAuditRun).where(AccountAuditRun.tenant_id == tenant.id)
    if platform:
        stmt = stmt.where(AccountAuditRun.platform == platform)
    if kind:
        stmt = stmt.where(AccountAuditRun.kind == kind)
    stmt = stmt.order_by(AccountAuditRun.created_at.desc(), AccountAuditRun.id.desc())
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/account-audit/runs/{run_id}", response_model=AccountAuditRunRead)
def get_account_audit_run_endpoint(
    run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> AccountAuditRun:
    run = db.get(AccountAuditRun, run_id)
    if not run or run.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="账号体检记录不存在")
    return run
