"""蒸馏:发起蒸馏(自动 top-N / 快照 / 手选,异步)+ 选材快照 CRUD + 蒸馏记录确认/放弃。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.blogger_distillation.note_ranking import rank_notes_by_need
from app.blogger_distillation.service import (
    abandon_blogger_distillation,
    confirm_blogger_distillation,
    create_snapshot,
    delete_snapshot,
    list_snapshots,
    update_snapshot,
)
from app.database import get_db
from app.models import (
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSnapshot,
    OperationTask,
    Tenant,
)
from app.queue import submit_background
from app.schemas import (
    BloggerDistillationRunRead,
    BloggerDistillRequest,
    BloggerSnapshotCreate,
    BloggerSnapshotRead,
    BloggerSnapshotUpdate,
    OperationTaskRead,
    SnapshotSuggestItem,
    SnapshotSuggestRequest,
    SnapshotSuggestResult,
)
from app.services.task_service import create_operation_task, run_blogger_distillation_task

router = APIRouter()


@router.post("/bloggers/{blogger_id}/distill", response_model=OperationTaskRead)
def distill_blogger_endpoint(
    blogger_id: int,
    payload: BloggerDistillRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")

    min_samples = settings.distill_min_samples
    snapshot_id: int | None = None

    if payload.source == "auto":
        # 自动蒸馏:取该博主 active 笔记里高赞 top-N（按 score 降序）。
        stmt = (
            select(BloggerPost.id)
            .where(
                BloggerPost.tenant_id == tenant.id,
                BloggerPost.blogger_id == blogger.id,
                BloggerPost.status != "delisted",
            )
            .order_by(BloggerPost.score.desc(), BloggerPost.id.desc())
            .limit(settings.blogger_auto_distill_top_n)
        )
        post_ids = list(db.scalars(stmt))
    else:
        # 自定义蒸馏:复用快照 或 手选笔记（手选自动存快照）。
        if payload.snapshot_id is not None:
            snapshot = db.get(BloggerSnapshot, payload.snapshot_id)
            if not snapshot or snapshot.tenant_id != tenant.id or snapshot.blogger_id != blogger.id:
                raise HTTPException(status_code=404, detail="快照不存在或不属于该博主")
            post_ids = snapshot.post_ids
            snapshot_id = snapshot.id
        elif payload.post_ids:
            # 校验所选笔记都属于该博主且未下架。
            valid_ids = set(
                db.scalars(
                    select(BloggerPost.id).where(
                        BloggerPost.tenant_id == tenant.id,
                        BloggerPost.blogger_id == blogger.id,
                        BloggerPost.status != "delisted",
                        BloggerPost.id.in_(payload.post_ids),
                    )
                )
            )
            post_ids = [pid for pid in payload.post_ids if pid in valid_ids]
            if len(post_ids) < min_samples:
                raise HTTPException(
                    status_code=400,
                    detail=f"自定义蒸馏至少需要 {min_samples} 篇有效笔记（建议 ≥{settings.distill_recommend_samples} 篇）",
                )
            try:
                name = payload.snapshot_name.strip() or f"自定义选材 · {len(post_ids)} 篇"
                snapshot = create_snapshot(db, tenant.id, blogger.id, name, post_ids)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            snapshot_id = snapshot.id
        else:
            raise HTTPException(status_code=400, detail="自定义蒸馏需要提供 snapshot_id 或 post_ids")

    if len(post_ids) < min_samples:
        raise HTTPException(
            status_code=400,
            detail=f"可用笔记不足 {min_samples} 篇（建议 ≥{settings.distill_recommend_samples} 篇），请先采集更多笔记",
        )

    task = create_operation_task(db, "blogger_distillation", tenant_id=tenant.id)
    submit_background(
        background_tasks,
        run_blogger_distillation_task,
        task.id,
        blogger.id,
        post_ids,
        payload.source,
        snapshot_id,
        payload.mode,
    )
    return task


def _valid_blogger_post_ids(db: Session, tenant_id: int, blogger_id: int, post_ids: list[int]) -> list[int]:
    """只保留属于该博主且未下架的笔记 id,保持入参顺序。"""
    valid = set(
        db.scalars(
            select(BloggerPost.id).where(
                BloggerPost.tenant_id == tenant_id,
                BloggerPost.blogger_id == blogger_id,
                BloggerPost.status != "delisted",
                BloggerPost.id.in_(post_ids),
            )
        )
    )
    return [pid for pid in post_ids if pid in valid]


def _require_min_snapshot_samples(post_ids: list[int]) -> None:
    if len(post_ids) < settings.distill_min_samples:
        raise HTTPException(
            status_code=400,
            detail=f"快照至少需要 {settings.distill_min_samples} 篇有效笔记（建议 ≥{settings.distill_recommend_samples} 篇）",
        )


@router.get("/bloggers/{blogger_id}/snapshots", response_model=list[BloggerSnapshotRead])
def list_snapshots_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerSnapshot]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    return list_snapshots(db, tenant.id, blogger_id)


@router.post("/bloggers/{blogger_id}/snapshots", response_model=BloggerSnapshotRead)
def create_snapshot_endpoint(
    blogger_id: int,
    payload: BloggerSnapshotCreate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerSnapshot:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    post_ids = _valid_blogger_post_ids(db, tenant.id, blogger_id, payload.post_ids)
    _require_min_snapshot_samples(post_ids)
    name = payload.name.strip() or f"自定义选材 · {len(post_ids)} 篇"
    try:
        return create_snapshot(db, tenant.id, blogger_id, name, post_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bloggers/{blogger_id}/snapshot-suggest", response_model=SnapshotSuggestResult)
def snapshot_suggest_endpoint(
    blogger_id: int,
    payload: SnapshotSuggestRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> SnapshotSuggestResult:
    """智能选材:按用户需求给该博主未下架笔记打相关度分,帮用户预选建快照。失败/无需求 → 空结果(前端退化手动)。"""
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    rows = db.execute(
        select(BloggerPost.id, BloggerPost.title, BloggerPost.content_subtype)
        .where(BloggerPost.tenant_id == tenant.id, BloggerPost.blogger_id == blogger_id, BloggerPost.status != "delisted")
        .order_by(BloggerPost.published_at.desc().nullslast(), BloggerPost.id.desc())
        .limit(150)
    ).all()
    notes = [{"id": r.id, "title": r.title or "", "subtype": r.content_subtype or ""} for r in rows]
    result = rank_notes_by_need(payload.need, notes, settings, timeout=settings.appraisal_llm_timeout)
    return SnapshotSuggestResult(
        suggested_name=result["name"],
        items=[SnapshotSuggestItem(post_id=it["post_id"], score=it["score"], reason=it["reason"]) for it in result["items"]],
    )


@router.patch("/bloggers/{blogger_id}/snapshots/{snapshot_id}", response_model=BloggerSnapshotRead)
def update_snapshot_endpoint(
    blogger_id: int,
    snapshot_id: int,
    payload: BloggerSnapshotUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerSnapshot:
    existing = db.get(BloggerSnapshot, snapshot_id)
    if not existing or existing.tenant_id != tenant.id or existing.blogger_id != blogger_id:
        raise HTTPException(status_code=404, detail="快照不存在或不属于该博主")
    post_ids: list[int] | None = None
    if payload.post_ids is not None:
        post_ids = _valid_blogger_post_ids(db, tenant.id, blogger_id, payload.post_ids)
        _require_min_snapshot_samples(post_ids)
    try:
        return update_snapshot(db, tenant.id, snapshot_id, name=payload.name, post_ids=post_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/bloggers/{blogger_id}/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot_endpoint(
    blogger_id: int,
    snapshot_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> None:
    snapshot = db.get(BloggerSnapshot, snapshot_id)
    if not snapshot or snapshot.tenant_id != tenant.id or snapshot.blogger_id != blogger_id:
        raise HTTPException(status_code=404, detail="快照不存在或不属于该博主")
    delete_snapshot(db, tenant.id, snapshot_id)


@router.get("/bloggers/{blogger_id}/distillation-runs", response_model=list[BloggerDistillationRunRead])
def list_blogger_runs_endpoint(
    blogger_id: int,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerDistillationRun]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    stmt = (
        select(BloggerDistillationRun)
        .where(BloggerDistillationRun.tenant_id == tenant.id, BloggerDistillationRun.blogger_id == blogger_id)
        .order_by(BloggerDistillationRun.created_at.desc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.post("/bloggers/{blogger_id}/distillation-runs/{run_id}/confirm", response_model=BloggerDistillationRunRead)
def confirm_blogger_run_endpoint(
    blogger_id: int,
    run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerDistillationRun:
    run = db.get(BloggerDistillationRun, run_id)
    if not run or run.tenant_id != tenant.id or run.blogger_id != blogger_id:
        raise HTTPException(status_code=404, detail="Distillation run not found")
    try:
        return confirm_blogger_distillation(db, tenant.id, run_id).run
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bloggers/{blogger_id}/distillation-runs/{run_id}/abandon", response_model=BloggerDistillationRunRead)
def abandon_blogger_run_endpoint(
    blogger_id: int,
    run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerDistillationRun:
    run = db.get(BloggerDistillationRun, run_id)
    if not run or run.tenant_id != tenant.id or run.blogger_id != blogger_id:
        raise HTTPException(status_code=404, detail="Distillation run not found")
    try:
        return abandon_blogger_distillation(db, tenant.id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
