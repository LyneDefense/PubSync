from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_tenant, settings
from app.database import get_db
from app.dashboard.service import build_account_dashboard, build_account_growth, build_overview
from app.models import AppSetting, Article, NewsItem, Tenant
from app.schemas import DashboardRead
from app.services.tenant_service import get_publishing_settings

router = APIRouter()

RangeQuery = Query(default="30d", pattern="^(7d|30d|all)$")


@router.get("/dashboard", response_model=DashboardRead)
def get_dashboard(tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> DashboardRead:
    news_count = db.scalar(select(func.count()).select_from(NewsItem).where(NewsItem.tenant_id == tenant.id)) or 0
    selected_count = (
        db.scalar(
            select(func.count()).select_from(NewsItem).where(NewsItem.tenant_id == tenant.id, NewsItem.selected.is_(True))
        )
        or 0
    )
    latest_article = db.scalar(
        select(Article).where(Article.tenant_id == tenant.id).order_by(Article.created_at.desc()).limit(1)
    )
    last_fetch_at = db.get(AppSetting, f"tenant:{tenant.id}:last_fetch_at")
    publishing = get_publishing_settings(db, tenant)
    schedule_label = {
        "daily": "每日",
        "weekly": f"每周{publishing.publish_weekday}",
        "monthly": f"每月{publishing.publish_month_day}日",
    }.get(publishing.publish_frequency, "每日")
    return DashboardRead(
        news_count=news_count,
        selected_count=selected_count,
        latest_article=latest_article,
        last_fetch_at=last_fetch_at.value if last_fetch_at else None,
        scheduled_publish_time=f"{schedule_label} {publishing.publish_time_hour:02d}:{publishing.publish_time_minute:02d}",
    )


# —— 效果看板 ——
@router.get("/dashboard/overview")
def dashboard_overview_endpoint(
    range: str = RangeQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    return build_overview(db, settings, tenant.id, range)


@router.get("/dashboard/account/{account_id}")
def dashboard_account_endpoint(
    account_id: int,
    range: str = RangeQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return build_account_dashboard(db, settings, tenant.id, account_id, range)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/dashboard/account/{account_id}/growth")
def dashboard_account_growth_endpoint(
    account_id: int,
    range: str = RangeQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return build_account_growth(db, tenant.id, account_id, range)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
