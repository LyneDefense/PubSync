from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_tenant
from app.database import get_db
from app.models import Article, OperationTask, Tenant
from app.queue import submit_background
from app.schemas import ArticleRead, ArticleUpdate, OperationTaskRead
from app.services.article_service import update_article
from app.services.task_service import create_operation_task, run_article_generation_task
from app.services.wechat_service import WeChatAPIError, send_article_to_wechat_draft

router = APIRouter()


@router.post("/articles/generate", response_model=OperationTaskRead)
def generate_article_endpoint(
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = create_operation_task(db, "article_generation", tenant_id=tenant.id)
    submit_background(background_tasks, run_article_generation_task, task.id)
    return task


@router.get("/articles/latest", response_model=ArticleRead | None)
def latest_article_endpoint(tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> Article | None:
    return db.scalar(select(Article).where(Article.tenant_id == tenant.id).order_by(Article.created_at.desc()).limit(1))


@router.patch("/articles/{article_id}", response_model=ArticleRead)
def update_article_endpoint(
    article_id: int,
    payload: ArticleUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> Article:
    article = db.get(Article, article_id)
    if not article or article.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Article not found")
    return update_article(db, article, **payload.model_dump(exclude_unset=True))


@router.post("/articles/{article_id}/send-to-wechat", response_model=ArticleRead)
def send_to_wechat_endpoint(
    article_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> Article:
    article = db.get(Article, article_id)
    if not article or article.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Article not found")
    try:
        return send_article_to_wechat_draft(db, article)
    except WeChatAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
