from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.blogger_distillation.search import search_bloggers
from app.blogger_distillation.service import (
    abandon_blogger_distillation,
    confirm_blogger_distillation,
    create_blogger,
    delete_blogger,
    set_blogger_favorite,
    update_blogger,
)
from app.blogger_distillation.tikhub_client import TikHubError
from app.database import get_db
from app.models import (
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
    OperationTask,
    Tenant,
)
from app.queue import submit_background
from app.schemas import (
    BloggerCollectRequest,
    BloggerCollectionRunRead,
    BloggerDistillationRunRead,
    BloggerDistillRequest,
    BloggerFavoriteUpdate,
    BloggerPostRead,
    BloggerProfileCreate,
    BloggerProfileRead,
    BloggerProfileUpdate,
    BloggerSearchResultRead,
    BloggerSkillRead,
    CollectEstimate,
    OperationTaskRead,
)
from app.services.task_service import (
    create_operation_task,
    run_blogger_collection_task,
    run_blogger_distillation_task,
)

router = APIRouter()


@router.get("/bloggers", response_model=list[BloggerProfileRead])
def list_bloggers_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerProfile]:
    stmt = (
        select(BloggerProfile)
        .where(BloggerProfile.tenant_id == tenant.id, BloggerProfile.platform == platform)
        .order_by(BloggerProfile.is_favorite.desc(), BloggerProfile.updated_at.desc(), BloggerProfile.id.desc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/bloggers/search", response_model=list[BloggerSearchResultRead])
def search_bloggers_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    keyword: str = Query(min_length=1, max_length=100),
    page: int = Query(default=1, ge=1, le=20),
    tenant: Tenant = Depends(current_tenant),
) -> list:
    _ = tenant
    try:
        return search_bloggers(settings, platform, keyword, page)
    except TikHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bloggers", response_model=BloggerProfileRead)
def create_blogger_endpoint(
    payload: BloggerProfileCreate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    try:
        return create_blogger(
            db,
            tenant.id,
            payload.platform,
            payload.external_id,
            payload.display_name,
            payload.homepage_url,
            payload.avatar_url,
            payload.follower_count,
            payload.niche,
            payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/bloggers/{blogger_id}", response_model=BloggerProfileRead)
def update_blogger_endpoint(
    blogger_id: int,
    payload: BloggerProfileUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    updates = payload.model_dump(exclude_unset=True)
    try:
        return update_blogger(db, tenant.id, blogger_id, **updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/bloggers/{blogger_id}/favorite", response_model=BloggerProfileRead)
def update_blogger_favorite_endpoint(
    blogger_id: int,
    payload: BloggerFavoriteUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    try:
        return set_blogger_favorite(db, tenant.id, blogger_id, payload.is_favorite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/bloggers/{blogger_id}", status_code=204)
def delete_blogger_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_blogger(db, tenant.id, blogger_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/bloggers/{blogger_id}/posts", response_model=list[BloggerPostRead])
def list_blogger_posts_endpoint(
    blogger_id: int,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerPost]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    stmt = (
        select(BloggerPost)
        .where(BloggerPost.tenant_id == tenant.id, BloggerPost.blogger_id == blogger_id)
        .order_by(BloggerPost.score.desc(), BloggerPost.created_at.desc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.post("/bloggers/{blogger_id}/collect", response_model=OperationTaskRead)
def collect_blogger_endpoint(
    blogger_id: int,
    payload: BloggerCollectRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    task = create_operation_task(db, "blogger_collection", tenant_id=tenant.id)
    submit_background(
        background_tasks,
        run_blogger_collection_task,
        task.id,
        blogger.id,
        payload.sample_limit,
        payload.comments_per_post,
        payload.asr_enabled,
    )
    return task


@router.get("/bloggers/{blogger_id}/collection-runs", response_model=list[BloggerCollectionRunRead])
def list_blogger_collection_runs_endpoint(
    blogger_id: int,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerCollectionRun]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    stmt = (
        select(BloggerCollectionRun)
        .where(BloggerCollectionRun.tenant_id == tenant.id, BloggerCollectionRun.blogger_id == blogger_id)
        .order_by(BloggerCollectionRun.created_at.desc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/bloggers/{blogger_id}/collection-runs/{collection_run_id}/posts", response_model=list[BloggerPostRead])
def list_blogger_collection_posts_endpoint(
    blogger_id: int,
    collection_run_id: int,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerPost]:
    collection_run = db.get(BloggerCollectionRun, collection_run_id)
    if not collection_run or collection_run.tenant_id != tenant.id or collection_run.blogger_id != blogger_id:
        raise HTTPException(status_code=404, detail="Collection run not found")
    stmt = (
        select(BloggerPost)
        .join(BloggerCollectionPost, BloggerCollectionPost.post_id == BloggerPost.id)
        .where(
            BloggerCollectionPost.collection_run_id == collection_run_id,
            BloggerCollectionPost.tenant_id == tenant.id,
            BloggerCollectionPost.blogger_id == blogger_id,
        )
        .order_by(BloggerCollectionPost.position.asc(), BloggerCollectionPost.id.asc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/bloggers/collect-estimate", response_model=CollectEstimate)
def collect_estimate_endpoint(
    sample_limit: int = Query(default=50, ge=5, le=200),
    comments_per_post: int = Query(default=20, ge=0, le=100),
    _: Tenant = Depends(current_tenant),
) -> CollectEstimate:
    # 每条样本约：1 次详情请求 +（评论开启时）1 次评论请求；再加搜索/资料/列表分页约 4 次固定开销。
    per_post = 1 + (1 if comments_per_post > 0 else 0)
    request_estimate = sample_limit * per_post + 4
    return CollectEstimate(
        sample_limit=sample_limit,
        comments_per_post=comments_per_post,
        request_estimate=request_estimate,
        cost_usd=round(request_estimate * settings.tikhub_request_price_usd, 4),
        cost_usd_min=round(request_estimate * settings.tikhub_min_request_price_usd, 4),
        cost_usd_max=round(request_estimate * settings.tikhub_max_request_price_usd, 4),
    )


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
    collection_run = db.get(BloggerCollectionRun, payload.collection_run_id)
    if not collection_run or collection_run.tenant_id != tenant.id or collection_run.blogger_id != blogger.id:
        raise HTTPException(status_code=404, detail="Collection run not found")
    if collection_run.status != "succeeded":
        raise HTTPException(status_code=400, detail="只能基于已完成的采集批次进行蒸馏")
    task = create_operation_task(db, "blogger_distillation", tenant_id=tenant.id)
    submit_background(
        background_tasks,
        run_blogger_distillation_task,
        task.id,
        blogger.id,
        payload.collection_run_id,
        payload.mode,
    )
    return task


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


@router.get("/blogger-skills", response_model=list[BloggerSkillRead])
def list_blogger_skills_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerSkill]:
    stmt = (
        select(BloggerSkill)
        .join(BloggerProfile, BloggerProfile.id == BloggerSkill.blogger_id)
        .where(BloggerSkill.tenant_id == tenant.id, BloggerProfile.platform == platform)
        .order_by(BloggerSkill.created_at.desc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))
