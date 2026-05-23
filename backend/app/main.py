from contextlib import asynccontextmanager
import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import create_db_and_tables, get_db
from app.models import AppSetting, Article, ContentProfile, LayoutSettings, NewsItem, OperationTask, OperationTaskEvent, Tenant, WeChatAccount
from app.schemas import (
    ArticleRead,
    ArticleUpdate,
    ContentProfileRead,
    DashboardRead,
    NewsItemRead,
    NewsItemUpdate,
    OperationTaskRead,
    OperationTaskEventRead,
    SettingRead,
    SettingUpdate,
    TenantRead,
    WeChatAccountRead,
    WorkspaceConfigRead,
    WorkspaceConfigUpdate,
)
from app.services.article_service import update_article
from app.services.auth_service import create_token, verify_credentials, verify_token
from app.services.news_service import list_news
from app.services.task_service import (
    create_operation_task,
    run_article_generation_task,
    run_news_fetch_task,
    scheduled_workspace_publish,
)
from app.services.tenant_service import (
    get_content_groups,
    get_default_tenant,
    get_layout_settings,
    get_profile,
    get_publishing_settings,
    get_tenant,
    get_wechat_account,
    list_tenants,
    update_layout_settings,
    update_content_groups,
    update_profile,
    update_publishing_settings,
    update_wechat_account,
)
from app.services.wechat_service import WeChatAPIError, send_article_to_wechat_draft


settings = get_settings()
Path(settings.static_dir).mkdir(parents=True, exist_ok=True)
logging.addLevelName(logging.DEBUG, "调试")
logging.addLevelName(logging.INFO, "信息")
logging.addLevelName(logging.WARNING, "警告")
logging.addLevelName(logging.ERROR, "错误")
logging.addLevelName(logging.CRITICAL, "严重")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    scheduler.add_job(
        scheduled_workspace_publish,
        "interval",
        minutes=1,
        id="workspace_daily_publish",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="PubSync API", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_auth(request: Request, call_next):
    path = request.url.path
    public_path = path == "/health" or path == "/auth/login" or path.startswith("/static/")
    if request.method == "OPTIONS" or public_path:
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not verify_token(token, settings):
        return JSONResponse({"detail": "请先登录"}, status_code=401)
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if not verify_credentials(payload.username, payload.password, settings):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(access_token=create_token(settings, payload.username))


def current_tenant(request: Request, db: Session = Depends(get_db)) -> Tenant:
    raw_tenant_id = request.headers.get("X-Tenant-ID")
    if not raw_tenant_id:
        return get_default_tenant(db)
    try:
        tenant_id = int(raw_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-ID 不合法") from exc
    try:
        return get_tenant(db, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/tenants", response_model=list[TenantRead])
def list_tenants_endpoint(db: Session = Depends(get_db)) -> list[Tenant]:
    return list_tenants(db)


@app.get("/profile", response_model=ContentProfileRead)
def get_profile_endpoint(tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> ContentProfile:
    return get_profile(db, tenant)


def read_wechat_account(account: WeChatAccount) -> WeChatAccountRead:
    return WeChatAccountRead(
        tenant_id=account.tenant_id,
        app_id=account.app_id,
        app_secret_configured=bool(account.app_secret),
    )


@app.get("/workspace/config", response_model=WorkspaceConfigRead)
def get_workspace_config_endpoint(
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> WorkspaceConfigRead:
    return WorkspaceConfigRead(
        profile=get_profile(db, tenant),
        wechat=read_wechat_account(get_wechat_account(db, tenant)),
        layout=get_layout_settings(db, tenant),
        publishing=get_publishing_settings(db, tenant),
        content_groups=get_content_groups(db, tenant),
    )


@app.put("/workspace/config", response_model=WorkspaceConfigRead)
def update_workspace_config_endpoint(
    payload: WorkspaceConfigUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> WorkspaceConfigRead:
    profile = get_profile(db, tenant)
    account = get_wechat_account(db, tenant)
    layout = get_layout_settings(db, tenant)
    publishing = get_publishing_settings(db, tenant)
    content_groups = get_content_groups(db, tenant)
    if payload.profile:
        profile = update_profile(db, tenant, payload.profile)
    if payload.wechat:
        account = update_wechat_account(db, tenant, payload.wechat)
    if payload.layout:
        layout = update_layout_settings(db, tenant, payload.layout)
    if payload.publishing:
        publishing = update_publishing_settings(db, tenant, payload.publishing)
    if payload.content_groups is not None:
        content_groups = update_content_groups(db, tenant, payload.content_groups)
    return WorkspaceConfigRead(
        profile=profile,
        wechat=read_wechat_account(account),
        layout=layout,
        publishing=publishing,
        content_groups=content_groups,
    )


@app.get("/dashboard", response_model=DashboardRead)
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
    return DashboardRead(
        news_count=news_count,
        selected_count=selected_count,
        latest_article=latest_article,
        last_fetch_at=last_fetch_at.value if last_fetch_at else None,
        scheduled_publish_time=f"{publishing.publish_time_hour:02d}:{publishing.publish_time_minute:02d}",
    )


@app.post("/news/fetch", response_model=OperationTaskRead)
def fetch_news_endpoint(
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = create_operation_task(db, "news_fetch", tenant_id=tenant.id)
    background_tasks.add_task(run_news_fetch_task, task.id)
    return task


@app.get("/news", response_model=list[NewsItemRead])
def list_news_endpoint(tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> list[NewsItem]:
    return list_news(db, tenant.id)


@app.patch("/news/{news_id}", response_model=NewsItemRead)
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


@app.post("/articles/generate", response_model=OperationTaskRead)
def generate_article_endpoint(
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = create_operation_task(db, "article_generation", tenant_id=tenant.id)
    background_tasks.add_task(run_article_generation_task, task.id)
    return task


@app.get("/tasks/{task_id}", response_model=OperationTaskRead)
def get_task_endpoint(task_id: str, tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/tasks/{task_id}/events", response_model=list[OperationTaskEventRead])
def list_task_events_endpoint(
    task_id: str,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[OperationTaskEvent]:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return list(
        db.scalars(
            select(OperationTaskEvent)
            .where(OperationTaskEvent.task_id == task_id, OperationTaskEvent.tenant_id == tenant.id)
            .order_by(OperationTaskEvent.created_at.asc(), OperationTaskEvent.id.asc())
        )
    )


@app.get("/articles/latest", response_model=ArticleRead | None)
def latest_article_endpoint(tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> Article | None:
    return db.scalar(select(Article).where(Article.tenant_id == tenant.id).order_by(Article.created_at.desc()).limit(1))


@app.patch("/articles/{article_id}", response_model=ArticleRead)
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


@app.post("/articles/{article_id}/send-to-wechat", response_model=ArticleRead)
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


@app.get("/settings", response_model=list[SettingRead])
def list_settings_endpoint(db: Session = Depends(get_db)) -> list[AppSetting]:
    return list(db.scalars(select(AppSetting).order_by(AppSetting.key.asc())))


@app.put("/settings/{key}", response_model=SettingRead)
def upsert_setting_endpoint(key: str, payload: SettingUpdate, db: Session = Depends(get_db)) -> AppSetting:
    setting = db.merge(AppSetting(key=key, value=payload.value))
    db.commit()
    db.refresh(setting)
    return setting
