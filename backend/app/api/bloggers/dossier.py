"""博主档案:一键建档 / 档案聚合读 / 笔记池同步 / 爆文归因。设计见 docs/博主档案页_流程设计.md。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_tenant, settings
from app.blogger_dossier.service import (
    dossier_overview,
    ensure_no_running_build,
    run_attribution_for_blogger,
)
from app.database import get_db
from app.models import BloggerProfile, OperationTask, Tenant
from app.queue import submit_background
from app.schemas import BloggerDossierRead, DossierPoolSyncRequest, OperationTaskRead
from app.services.task_service import (
    create_operation_task,
    run_blogger_dossier_task,
    run_blogger_pool_sync_task,
    run_blogger_redistill_task,
)

router = APIRouter()


def _get_blogger_or_404(db: Session, tenant: Tenant, blogger_id: int) -> BloggerProfile:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    return blogger


def _ensure_idle_or_409(db: Session, blogger: BloggerProfile) -> None:
    try:
        ensure_no_running_build(db, blogger)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/bloggers/{blogger_id}/dossier", response_model=BloggerDossierRead)
def get_blogger_dossier_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    _get_blogger_or_404(db, tenant, blogger_id)
    return dossier_overview(db, settings, tenant.id, blogger_id)


@router.post("/bloggers/{blogger_id}/dossier/build", response_model=OperationTaskRead)
def build_blogger_dossier_endpoint(
    blogger_id: int,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    """一键建档:资料 → 全量笔记池 → 统计/轨迹 → 最新 N 篇详情 → 自动蒸馏默认画像(长任务)。"""
    blogger = _get_blogger_or_404(db, tenant, blogger_id)
    _ensure_idle_or_409(db, blogger)
    task = create_operation_task(db, "blogger_dossier", tenant_id=tenant.id)
    submit_background(background_tasks, run_blogger_dossier_task, task.id, blogger.id)
    return task


@router.post("/bloggers/{blogger_id}/dossier/redistill", response_model=OperationTaskRead)
def redistill_blogger_dossier_endpoint(
    blogger_id: int,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    """更新画像(轻量重蒸):用现有详情池重新选样 + 蒸馏,不重拉平台(长任务)。"""
    blogger = _get_blogger_or_404(db, tenant, blogger_id)
    _ensure_idle_or_409(db, blogger)
    task = create_operation_task(db, "blogger_redistill", tenant_id=tenant.id)
    submit_background(background_tasks, run_blogger_redistill_task, task.id, blogger.id)
    return task


@router.post("/bloggers/{blogger_id}/dossier/pool/sync", response_model=OperationTaskRead)
def sync_blogger_pool_endpoint(
    blogger_id: int,
    payload: DossierPoolSyncRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    """笔记池同步:incremental=增量(默认,遇到整段已知即停);full=全量校准。"""
    blogger = _get_blogger_or_404(db, tenant, blogger_id)
    _ensure_idle_or_409(db, blogger)
    task = create_operation_task(db, "blogger_pool_sync", tenant_id=tenant.id)
    submit_background(background_tasks, run_blogger_pool_sync_task, task.id, blogger.id, payload.mode)
    return task


@router.post("/bloggers/{blogger_id}/dossier/attribution")
def run_blogger_attribution_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """爆文归因(同步,LLM 一次调用):基于轨迹爆发点生成"有据的假设"。无爆发点 → 400 诚实拒绝。"""
    _get_blogger_or_404(db, tenant, blogger_id)
    try:
        return run_attribution_for_blogger(db, settings, tenant.id, blogger_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
