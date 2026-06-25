from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.benchmark_discovery import flow
from app.benchmark_discovery.engine import popularity_score
from app.benchmark_discovery.service import evaluate_one
from app.skill_optimization.service import confirm_skill_optimization
from app.blogger_distillation.search import search_bloggers
from app.blogger_distillation.service import (
    abandon_blogger_distillation,
    confirm_blogger_distillation,
    create_blogger,
    create_snapshot,
    delete_blogger,
    delete_snapshot,
    list_snapshots,
    refresh_blogger_profile,
    set_blogger_favorite,
    update_blogger,
    update_snapshot,
)
from app.blogger_distillation.tikhub_client import TikHubError
from app.database import get_db
from app.models import (
    BenchmarkDiscoverySession,
    BenchmarkRecommendationRun,
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
    BloggerSnapshot,
    OperationTask,
    SkillTrainingRun,
    Tenant,
)
from app.queue import submit_background
from app.schemas import (
    BloggerCollectRequest,
    BloggerUrlCollectRequest,
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
    BloggerSnapshotCreate,
    BloggerSnapshotRead,
    BloggerSnapshotUpdate,
    CollectEstimate,
    OperationTaskRead,
)
from app.schemas.benchmark import (
    BenchmarkRecommendationRunRead,
    DiscoveryDirectionsRequest,
    DiscoveryReviewRequest,
    DiscoveryStartRequest,
    EvaluateRequest,
    EvaluateResult,
    RecommendRequest,
)
from app.schemas.skill_training import SkillOptimizeConfirm, SkillOptimizeRequest, SkillTrainingRunRead
from app.services.task_service import (
    create_operation_task,
    run_benchmark_recommend_task,
    run_blogger_collection_task,
    run_blogger_distillation_task,
    run_blogger_url_collection_task,
    run_discovery_recall_task,
    run_skill_optimization_task,
)

router = APIRouter()


@router.get("/bloggers", response_model=list[BloggerProfileRead])
def list_bloggers_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    account_type: str | None = Query(default=None, pattern="^(benchmark|mine)$"),
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
    if account_type:
        stmt = stmt.where(BloggerProfile.account_type == account_type)
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
        results = search_bloggers(settings, platform, keyword, page)
    except TikHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # 附火爆度速览(仅按粉丝数粗算,免费);完整四项指标要点「评估」才跑。
    return [{**r.__dict__, "quick_popularity": popularity_score(r.follower_count, [])} for r in results]


def _require_my_account(db: Session, tenant_id: int, account_id: int) -> BloggerProfile:
    blogger = db.get(BloggerProfile, account_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="我的账号不存在")
    if blogger.account_type != "mine":
        raise HTTPException(status_code=400, detail="所选账号不是「我的账号」")
    return blogger


@router.post("/bloggers/recommend", response_model=OperationTaskRead)
def recommend_bloggers_endpoint(
    payload: RecommendRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    """智能推荐:按意图帮用户找对标博主(异步任务,结果落 BenchmarkRecommendationRun)。"""
    if payload.my_account_id:
        _require_my_account(db, tenant.id, payload.my_account_id)
    task = create_operation_task(db, "benchmark_recommend", tenant_id=tenant.id)
    submit_background(
        background_tasks,
        run_benchmark_recommend_task,
        task.id,
        {
            "platform": payload.platform,
            "intent": payload.intent.model_dump(),
            "my_account_id": payload.my_account_id,
        },
    )
    return task


@router.get("/bloggers/recommend/runs", response_model=list[BenchmarkRecommendationRunRead])
def list_recommend_runs_endpoint(
    platform: str | None = None,
    task_id: str | None = None,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BenchmarkRecommendationRun]:
    stmt = select(BenchmarkRecommendationRun).where(BenchmarkRecommendationRun.tenant_id == tenant.id)
    if platform:
        stmt = stmt.where(BenchmarkRecommendationRun.platform == platform)
    if task_id:
        stmt = stmt.where(BenchmarkRecommendationRun.task_id == task_id)
    stmt = stmt.order_by(BenchmarkRecommendationRun.created_at.desc(), BenchmarkRecommendationRun.id.desc())
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/bloggers/recommend/runs/{run_id}", response_model=BenchmarkRecommendationRunRead)
def get_recommend_run_endpoint(
    run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BenchmarkRecommendationRun:
    run = db.get(BenchmarkRecommendationRun, run_id)
    if not run or run.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="推荐记录不存在")
    return run


@router.post("/bloggers/evaluate", response_model=EvaluateResult)
def evaluate_blogger_endpoint(
    payload: EvaluateRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> EvaluateResult:
    """单博主评分(同步):候选来自搜索结果或粘贴主页链接。"""
    if payload.my_account_id:
        _require_my_account(db, tenant.id, payload.my_account_id)
    try:
        score = evaluate_one(
            db=db,
            settings=settings,
            tenant_id=tenant.id,
            platform=payload.platform,
            intent=payload.intent.model_dump(),
            my_account_id=payload.my_account_id,
            candidate=payload.candidate.model_dump() if payload.candidate else None,
            homepage_url=payload.homepage_url,
        )
    except TikHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EvaluateResult(candidate=score)


# —— 泛搜索(发现会话)——
def _discovery_or_404(db: Session, tenant_id: int, session_id: int) -> BenchmarkDiscoverySession:
    sess = db.get(BenchmarkDiscoverySession, session_id)
    if not sess or sess.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="发现会话不存在")
    if sess.status == "expired":
        raise HTTPException(status_code=410, detail="本次发现会话已过期，请重新开始")
    return sess


def _discovery_todo(sess: BenchmarkDiscoverySession) -> dict:
    rec = flow.recommend_next(sess, has_seed_picks=bool(sess.seeds)) if sess.stage == "review_candidates" else None
    return flow.build_todo(sess, recommended=rec)


@router.post("/benchmark/discovery/start")
def discovery_start_endpoint(
    payload: DiscoveryStartRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    try:
        sess = flow.start_session(db, settings, tenant.id, payload.platform, payload.domains, payload.my_account_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _discovery_todo(sess)


@router.get("/benchmark/discovery/{session_id}")
def discovery_todo_endpoint(
    session_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    return _discovery_todo(_discovery_or_404(db, tenant.id, session_id))


@router.post("/benchmark/discovery/{session_id}/directions", response_model=OperationTaskRead)
def discovery_directions_endpoint(
    session_id: int,
    payload: DiscoveryDirectionsRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    sess = _discovery_or_404(db, tenant.id, session_id)
    flow.submit_directions(db, settings, sess, [d.model_dump() for d in payload.directions])
    task = create_operation_task(db, "discovery_recall", tenant_id=tenant.id)
    sess.task_id = task.id
    db.commit()
    submit_background(background_tasks, run_discovery_recall_task, task.id, sess.id)
    return task


@router.post("/benchmark/discovery/{session_id}/review")
def discovery_review_endpoint(
    session_id: int,
    payload: DiscoveryReviewRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    sess = _discovery_or_404(db, tenant.id, session_id)
    choice = flow.submit_review(db, settings, sess, payload.adopt_ids, payload.seed_ids, payload.choice, payload.text)
    if choice in ("more", "seed_more"):
        task = create_operation_task(db, "discovery_recall", tenant_id=tenant.id)
        sess.task_id = task.id
        db.commit()
        submit_background(background_tasks, run_discovery_recall_task, task.id, sess.id)
        return {"mode": "recall", "task_id": task.id}
    if choice == "change_directions":
        return {"mode": "todo", "todo": _discovery_todo(sess)}
    created = flow.checkout(db, sess)
    return {"mode": "done", "todo": flow.build_todo(sess), "created": len(created)}


@router.post("/benchmark/discovery/{session_id}/checkout")
def discovery_checkout_endpoint(
    session_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    sess = _discovery_or_404(db, tenant.id, session_id)
    created = flow.checkout(db, sess)
    return {"mode": "done", "todo": flow.build_todo(sess), "created": len(created)}


# —— Skill 优化(训练)——
@router.post("/bloggers/{blogger_id}/optimize-skill", response_model=OperationTaskRead)
def optimize_skill_endpoint(
    blogger_id: int,
    payload: SkillOptimizeRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="博主不存在")
    if payload.skill_id is not None:
        chosen = db.get(BloggerSkill, payload.skill_id)
        if not chosen or chosen.tenant_id != tenant.id or chosen.blogger_id != blogger_id:
            raise HTTPException(status_code=400, detail="指定的 Skill 不存在或不属于该博主")
    else:
        has_skill = db.scalar(
            select(BloggerSkill).where(BloggerSkill.blogger_id == blogger_id, BloggerSkill.status == "active")
        )
        if not has_skill:
            raise HTTPException(status_code=400, detail="该博主还没有 active Skill,请先去蒸馏")
    task = create_operation_task(db, "skill_optimization", tenant_id=tenant.id)
    submit_background(
        background_tasks, run_skill_optimization_task, task.id,
        {"blogger_id": blogger_id, "epochs": payload.epochs, "skill_id": payload.skill_id},
    )
    return task


@router.get("/skill-training/runs", response_model=list[SkillTrainingRunRead])
def list_skill_training_runs_endpoint(
    blogger_id: int | None = None,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[SkillTrainingRun]:
    stmt = select(SkillTrainingRun).where(SkillTrainingRun.tenant_id == tenant.id)
    if blogger_id:
        stmt = stmt.where(SkillTrainingRun.blogger_id == blogger_id)
    stmt = stmt.order_by(SkillTrainingRun.created_at.desc(), SkillTrainingRun.id.desc())
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/skill-training/runs/{run_id}", response_model=SkillTrainingRunRead)
def get_skill_training_run_endpoint(
    run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> SkillTrainingRun:
    run = db.get(SkillTrainingRun, run_id)
    if not run or run.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="优化记录不存在")
    return run


@router.post("/skill-training/runs/{run_id}/confirm", response_model=SkillTrainingRunRead)
def confirm_skill_training_run_endpoint(
    run_id: int,
    payload: SkillOptimizeConfirm,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> SkillTrainingRun:
    try:
        return confirm_skill_optimization(db, tenant.id, run_id, payload.adopt)
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
            account_type=payload.account_type,
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


@router.post("/bloggers/{blogger_id}/refresh-profile", response_model=BloggerProfileRead)
def refresh_blogger_profile_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    try:
        return refresh_blogger_profile(db, settings, tenant.id, blogger_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TikHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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


@router.get("/blogger-skills", response_model=list[BloggerSkillRead])
def list_blogger_skills_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    blogger_id: int | None = None,
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
    if blogger_id:
        stmt = stmt.where(BloggerSkill.blogger_id == blogger_id)
    return list(db.scalars(apply_pagination(stmt, limit, offset)))
