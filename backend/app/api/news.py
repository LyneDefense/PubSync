from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, current_tenant
from app.database import get_db
from app.models import NewsItem, OperationTask, Tenant
from app.queue import submit_background
from app.schemas import NewsItemRead, NewsItemUpdate, OperationTaskRead
from app.services.news_service import list_news
from app.services.task_service import create_operation_task, run_news_fetch_task

router = APIRouter()


@router.post("/news/fetch", response_model=OperationTaskRead)
def fetch_news_endpoint(
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = create_operation_task(db, "news_fetch", tenant_id=tenant.id)
    submit_background(background_tasks, run_news_fetch_task, task.id)
    return task


@router.get("/news", response_model=list[NewsItemRead])
def list_news_endpoint(
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[NewsItem]:
    return list_news(db, tenant.id, limit=limit, offset=offset)


@router.patch("/news/{news_id}", response_model=NewsItemRead)
def update_news_endpoint(
    news_id: int,
    payload: NewsItemUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> NewsItem:
    news = db.get(NewsItem, news_id)
    if not news or news.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="News item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(news, key, value)
    db.commit()
    db.refresh(news)
    return news
