"""泛搜索 / 找相似 工作台(/benchmark/discovery/*):领域→选角度→召回→候选采用→存对标库。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_tenant, settings
from app.benchmark_discovery import flow
from app.database import get_db
from app.models import BenchmarkDiscoverySession, OperationTask, Tenant
from app.queue import submit_background
from app.schemas import OperationTaskRead
from app.schemas.benchmark import (
    DiscoveryAngleRequest,
    DiscoveryOpRequest,
    DiscoverySimilarRequest,
    DiscoveryStartRequest,
)
from app.services.task_service import create_operation_task, run_discovery_recall_task

router = APIRouter()


def _discovery_or_404(db: Session, tenant_id: int, session_id: int) -> BenchmarkDiscoverySession:
    sess = db.get(BenchmarkDiscoverySession, session_id)
    if not sess or sess.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="发现会话不存在")
    if sess.status == "expired":
        raise HTTPException(status_code=410, detail="本次发现会话已过期，请重新开始")
    return sess


@router.post("/benchmark/discovery/start")
def discovery_start_endpoint(
    payload: DiscoveryStartRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """泛搜索:领域 → 进入「选细分角度」阶段。"""
    try:
        sess = flow.start_broad(db, settings, tenant.id, payload.platform, payload.domains)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return flow.build_workspace(sess, settings)


@router.post("/benchmark/discovery/similar")
def discovery_similar_endpoint(
    payload: DiscoverySimilarRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """找相似:从对标库挑博主 → 直接进候选阶段(关键词取自其存量笔记)。"""
    try:
        sess = flow.start_similar(db, settings, tenant.id, payload.platform, payload.blogger_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return flow.build_workspace(sess, settings)


@router.get("/benchmark/discovery/{session_id}")
def discovery_workspace_endpoint(
    session_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    return flow.build_workspace(_discovery_or_404(db, tenant.id, session_id), settings)


@router.post("/benchmark/discovery/{session_id}/angles")
def discovery_angles_endpoint(
    session_id: int,
    payload: DiscoveryAngleRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """角度收窄(同步):toggle 选/取消、reject 排除、propose 再推一批、begin 开始搜。"""
    sess = _discovery_or_404(db, tenant.id, session_id)
    try:
        flow.angle_op(db, settings, sess, payload.op, payload.labels)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return flow.build_workspace(sess, settings)


@router.post("/benchmark/discovery/{session_id}/recall", response_model=OperationTaskRead)
def discovery_recall_endpoint(
    session_id: int,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    """找候选(异步):按选中角度/关键词召回,追加到候选池。"""
    sess = _discovery_or_404(db, tenant.id, session_id)
    if not flow.selected_domains(sess):
        raise HTTPException(status_code=400, detail="还没有可搜的角度，先选/开始")
    task = create_operation_task(db, "discovery_recall", tenant_id=tenant.id)
    sess.task_id = task.id
    db.commit()
    submit_background(background_tasks, run_discovery_recall_task, task.id, sess.id)
    return task


@router.post("/benchmark/discovery/{session_id}/op")
def discovery_op_endpoint(
    session_id: int,
    payload: DiscoveryOpRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """候选阶段:采用 / 不要 / 移除已选 / 清空候选(同步)。"""
    sess = _discovery_or_404(db, tenant.id, session_id)
    if payload.op == "adopt":
        flow.adopt_candidates(db, settings, sess, payload.ids)
    elif payload.op == "dismiss":
        flow.dismiss_candidates(db, settings, sess, payload.ids)
    elif payload.op == "remove_selected":
        flow.remove_selected(db, settings, sess, payload.ids)
    elif payload.op == "clear_candidates":
        flow.clear_candidates(db, settings, sess)
    return flow.build_workspace(sess, settings)


@router.post("/benchmark/discovery/{session_id}/save")
def discovery_save_endpoint(
    session_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    """把已选列表保存到对标库(幂等,可随时存)。"""
    sess = _discovery_or_404(db, tenant.id, session_id)
    created = flow.save_selected(db, sess)
    return {"created": len(created), "workspace": flow.build_workspace(sess, settings)}
