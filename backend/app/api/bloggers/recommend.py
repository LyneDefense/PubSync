"""对标发现「评分」侧:关键词搜索、智能推荐(异步)、单博主评分(同步)。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.benchmark_discovery.engine import popularity_score
from app.benchmark_discovery.service import evaluate_one
from app.blogger_distillation.search import search_bloggers
from app.blogger_distillation.tikhub_client import TikHubError
from app.database import get_db
from app.models import BenchmarkRecommendationRun, BloggerProfile, Tenant
from app.queue import submit_background
from app.schemas import BloggerSearchResultRead, OperationTaskRead
from app.schemas.benchmark import (
    BenchmarkRecommendationRunRead,
    EvaluateRequest,
    EvaluateResult,
    RecommendRequest,
)
from app.services.task_service import create_operation_task, run_benchmark_recommend_task

router = APIRouter()


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
