"""笔记采集:主页增量采集 / 粘贴 URL 定向采集(均异步)+ 采集批次查询 + 成本预估。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.database import get_db
from app.models import (
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerPost,
    BloggerProfile,
    OperationTask,
    Tenant,
)
from app.queue import submit_background
from app.schemas import (
    BloggerCollectionRunRead,
    BloggerCollectRequest,
    BloggerPostRead,
    BloggerUrlCollectRequest,
    CollectEstimate,
    OperationTaskRead,
)
from app.services.task_service import (
    create_operation_task,
    run_blogger_collection_task,
    run_blogger_url_collection_task,
)

router = APIRouter()


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
        settings.asr_enabled,  # ASR 只由后台全局开关控制,用户端不再可选
        payload.content_types,
        payload.order,
        payload.fetch_all,
    )
    return task


@router.post("/bloggers/{blogger_id}/collect-by-urls", response_model=OperationTaskRead)
def collect_blogger_by_urls_endpoint(
    blogger_id: int,
    payload: BloggerUrlCollectRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    if blogger.platform != "xhs":
        raise HTTPException(status_code=400, detail="目前仅支持小红书笔记链接定向采集")
    task = create_operation_task(db, "blogger_collection", tenant_id=tenant.id)
    submit_background(
        background_tasks,
        run_blogger_url_collection_task,
        task.id,
        blogger.id,
        payload.urls,
        payload.comments_per_post,
        settings.asr_enabled,  # ASR 只由后台全局开关控制,用户端不再可选
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
