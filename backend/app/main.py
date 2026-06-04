from contextlib import asynccontextmanager
import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import create_db_and_tables, get_db
from app.models import (
    AppSetting,
    Article,
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
    ContentProfile,
    LayoutSettings,
    NewsItem,
    OperationTask,
    OperationTaskEvent,
    Tenant,
    TenantStatus,
    User,
    WeChatAccount,
    XhsPublishPackage,
)
from app.schemas import (
    AdminUserCreate,
    AdminUserRead,
    ArticleRead,
    ArticleUpdate,
    BloggerCollectRequest,
    BloggerCollectionRunRead,
    BloggerDistillRequest,
    BloggerDistillationRunRead,
    BloggerPostRead,
    BloggerProfileCreate,
    BloggerProfileRead,
    BloggerSearchResultRead,
    BloggerSkillRead,
    ContentProfileRead,
    CurrentUserRead,
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
    XhsPublishPackageCreate,
    XhsPublishPackageDraftRead,
    XhsPublishPackageRead,
    XhsPublishPackageSave,
    XhsTopicIdeaRequest,
    XhsTopicIdeaResponse,
)
from app.services.article_service import update_article
from app.services.ai_service import AIServiceError
from app.services.auth_service import (
    create_token,
    get_user_by_username,
    hash_password,
    is_admin_user,
    tenant_ids_for_user,
    token_username,
    verify_credentials,
    verify_token,
)
from app.services.news_service import list_news
from app.services.task_service import (
    create_operation_task,
    request_task_cancel,
    run_blogger_collection_task,
    run_blogger_distillation_task,
    run_article_generation_task,
    run_news_fetch_task,
    run_xhs_package_draft_task,
    scheduled_workspace_publish,
)
from app.blogger_distillation.service import abandon_blogger_distillation, confirm_blogger_distillation, create_blogger
from app.blogger_distillation.search import search_bloggers
from app.blogger_distillation.tikhub_client import TikHubError
from app.services.tenant_service import (
    ensure_tenant_defaults,
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
from app.xhs_creation.service import (
    create_xhs_publish_package,
    generate_xhs_publish_package_draft,
    generate_xhs_topic_ideas,
)


settings = get_settings()
Path(settings.static_dir).mkdir(parents=True, exist_ok=True)
logging.addLevelName(logging.DEBUG, "调试")
logging.addLevelName(logging.INFO, "信息")
logging.addLevelName(logging.WARNING, "警告")
logging.addLevelName(logging.ERROR, "错误")
logging.addLevelName(logging.CRITICAL, "严重")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


class HealthAccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            return str(args[2]).split("?", 1)[0] != "/health"
        return "/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(HealthAccessLogFilter())
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
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    if not verify_credentials(payload.username, payload.password, settings, db):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(access_token=create_token(settings, payload.username))


def current_username(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="请先登录")
    username = token_username(token, settings)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")
    return username


def current_tenant(request: Request, db: Session = Depends(get_db)) -> Tenant:
    username = current_username(request)
    allowed_tenant_ids = tenant_ids_for_user(username, settings, db)
    if not allowed_tenant_ids:
        raise HTTPException(status_code=403, detail="当前账号没有可访问的工作空间")

    raw_tenant_id = request.headers.get("X-Tenant-ID")
    if not raw_tenant_id:
        tenant_id = allowed_tenant_ids[0]
    else:
        try:
            tenant_id = int(raw_tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="X-Tenant-ID 不合法") from exc
    if tenant_id not in allowed_tenant_ids:
        raise HTTPException(status_code=403, detail="当前账号不能访问该工作空间")
    try:
        return get_tenant(db, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def require_admin(request: Request, db: Session = Depends(get_db)) -> str:
    username = current_username(request)
    if not is_admin_user(username, settings, db):
        raise HTTPException(status_code=403, detail="只有管理员可以访问后台管理")
    return username


@app.get("/auth/me", response_model=CurrentUserRead)
def me_endpoint(request: Request, db: Session = Depends(get_db)) -> CurrentUserRead:
    username = current_username(request)
    user = get_user_by_username(db, username)
    if user:
        return CurrentUserRead(username=user.username, is_admin=user.is_admin, tenant_id=user.tenant_id)
    tenant_ids = tenant_ids_for_user(username, settings, db)
    return CurrentUserRead(
        username=username,
        is_admin=is_admin_user(username, settings, db),
        tenant_id=tenant_ids[0] if tenant_ids else None,
    )


@app.get("/tenants", response_model=list[TenantRead])
def list_tenants_endpoint(request: Request, db: Session = Depends(get_db)) -> list[Tenant]:
    username = current_username(request)
    allowed_tenant_ids = tenant_ids_for_user(username, settings, db)
    tenants = [tenant for tenant in list_tenants(db) if tenant.id in allowed_tenant_ids]
    if not tenants:
        raise HTTPException(status_code=403, detail="当前账号没有可访问的工作空间")
    return tenants


@app.get("/admin/users", response_model=list[AdminUserRead])
def admin_list_users_endpoint(
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())))


@app.post("/admin/users", response_model=AdminUserRead)
def admin_create_user_endpoint(
    payload: AdminUserCreate,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    username = payload.username.strip()
    if get_user_by_username(db, username):
        raise HTTPException(status_code=409, detail="账号已存在")
    slug = normalize_tenant_slug(payload.tenant_slug or username)
    if db.scalar(select(Tenant).where(Tenant.slug == slug)):
        raise HTTPException(status_code=409, detail="工作空间标识已存在")
    tenant = Tenant(name=payload.tenant_name.strip(), slug=slug, status=TenantStatus.active)
    db.add(tenant)
    db.flush()
    ensure_tenant_defaults(db, tenant)
    user = User(
        username=username,
        password_hash=hash_password(payload.password, settings),
        is_admin=payload.is_admin,
        tenant_id=tenant.id,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def normalize_tenant_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_").lower()
    return slug[:80] or "workspace"


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


@app.get("/bloggers", response_model=list[BloggerProfileRead])
def list_bloggers_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerProfile]:
    return list(
        db.scalars(
            select(BloggerProfile)
            .where(BloggerProfile.tenant_id == tenant.id, BloggerProfile.platform == platform)
            .order_by(BloggerProfile.updated_at.desc(), BloggerProfile.id.desc())
        )
    )


@app.get("/bloggers/search", response_model=list[BloggerSearchResultRead])
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


@app.post("/bloggers", response_model=BloggerProfileRead)
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


@app.get("/bloggers/{blogger_id}/posts", response_model=list[BloggerPostRead])
def list_blogger_posts_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerPost]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    return list(
        db.scalars(
            select(BloggerPost)
            .where(BloggerPost.tenant_id == tenant.id, BloggerPost.blogger_id == blogger_id)
            .order_by(BloggerPost.score.desc(), BloggerPost.created_at.desc())
        )
    )


@app.post("/bloggers/{blogger_id}/collect", response_model=OperationTaskRead)
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
    background_tasks.add_task(
        run_blogger_collection_task,
        task.id,
        blogger.id,
        payload.sample_limit,
        payload.comments_per_post,
        payload.asr_enabled,
    )
    return task


@app.get("/bloggers/{blogger_id}/collection-runs", response_model=list[BloggerCollectionRunRead])
def list_blogger_collection_runs_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerCollectionRun]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    return list(
        db.scalars(
            select(BloggerCollectionRun)
            .where(BloggerCollectionRun.tenant_id == tenant.id, BloggerCollectionRun.blogger_id == blogger_id)
            .order_by(BloggerCollectionRun.created_at.desc())
        )
    )


@app.get("/bloggers/{blogger_id}/collection-runs/{collection_run_id}/posts", response_model=list[BloggerPostRead])
def list_blogger_collection_posts_endpoint(
    blogger_id: int,
    collection_run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerPost]:
    collection_run = db.get(BloggerCollectionRun, collection_run_id)
    if not collection_run or collection_run.tenant_id != tenant.id or collection_run.blogger_id != blogger_id:
        raise HTTPException(status_code=404, detail="Collection run not found")
    return list(
        db.scalars(
            select(BloggerPost)
            .join(BloggerCollectionPost, BloggerCollectionPost.post_id == BloggerPost.id)
            .where(
                BloggerCollectionPost.collection_run_id == collection_run_id,
                BloggerCollectionPost.tenant_id == tenant.id,
                BloggerCollectionPost.blogger_id == blogger_id,
            )
            .order_by(BloggerCollectionPost.position.asc(), BloggerCollectionPost.id.asc())
        )
    )


@app.post("/bloggers/{blogger_id}/distill", response_model=OperationTaskRead)
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
    background_tasks.add_task(
        run_blogger_distillation_task,
        task.id,
        blogger.id,
        payload.collection_run_id,
    )
    return task


@app.get("/bloggers/{blogger_id}/distillation-runs", response_model=list[BloggerDistillationRunRead])
def list_blogger_runs_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerDistillationRun]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    return list(
        db.scalars(
            select(BloggerDistillationRun)
            .where(BloggerDistillationRun.tenant_id == tenant.id, BloggerDistillationRun.blogger_id == blogger_id)
            .order_by(BloggerDistillationRun.created_at.desc())
        )
    )


@app.post("/bloggers/{blogger_id}/distillation-runs/{run_id}/confirm", response_model=BloggerDistillationRunRead)
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


@app.post("/bloggers/{blogger_id}/distillation-runs/{run_id}/abandon", response_model=BloggerDistillationRunRead)
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


@app.get("/blogger-skills", response_model=list[BloggerSkillRead])
def list_blogger_skills_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerSkill]:
    return list(
        db.scalars(
            select(BloggerSkill)
            .join(BloggerProfile, BloggerProfile.id == BloggerSkill.blogger_id)
            .where(BloggerSkill.tenant_id == tenant.id, BloggerProfile.platform == platform)
            .order_by(BloggerSkill.created_at.desc())
        )
    )


@app.get("/xhs/publish-packages", response_model=list[XhsPublishPackageRead])
def list_xhs_publish_packages_endpoint(
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[XhsPublishPackage]:
    return list(
        db.scalars(
            select(XhsPublishPackage)
            .where(XhsPublishPackage.tenant_id == tenant.id)
            .order_by(XhsPublishPackage.created_at.desc(), XhsPublishPackage.id.desc())
        )
    )


@app.post("/xhs/publish-packages", response_model=XhsPublishPackageRead)
def create_xhs_publish_package_endpoint(
    payload: XhsPublishPackageSave,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> XhsPublishPackage:
    try:
        return create_xhs_publish_package(db, tenant.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/xhs/package-drafts", response_model=XhsPublishPackageDraftRead)
def generate_xhs_publish_package_draft_endpoint(
    payload: XhsPublishPackageCreate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return generate_xhs_publish_package_draft(db, settings, tenant.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/xhs/package-drafts/generate", response_model=OperationTaskRead)
def generate_xhs_publish_package_draft_task_endpoint(
    payload: XhsPublishPackageCreate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = create_operation_task(db, "xhs_package_draft", tenant_id=tenant.id)
    background_tasks.add_task(run_xhs_package_draft_task, task.id, payload.model_dump())
    return task


@app.post("/xhs/topic-ideas", response_model=XhsTopicIdeaResponse)
def generate_xhs_topic_ideas_endpoint(
    payload: XhsTopicIdeaRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return {"ideas": generate_xhs_topic_ideas(db, settings, tenant.id, payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/tasks/{task_id}", response_model=OperationTaskRead)
def get_task_endpoint(task_id: str, tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/cancel", response_model=OperationTaskRead)
def cancel_task_endpoint(task_id: str, tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type != "blogger_distillation":
        raise HTTPException(status_code=400, detail="Only blogger distillation tasks can be stopped")
    request_task_cancel(db, task)
    db.refresh(task)
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
def list_settings_endpoint(_: str = Depends(require_admin), db: Session = Depends(get_db)) -> list[AppSetting]:
    return list(db.scalars(select(AppSetting).order_by(AppSetting.key.asc())))


@app.put("/settings/{key}", response_model=SettingRead)
def upsert_setting_endpoint(
    key: str,
    payload: SettingUpdate,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AppSetting:
    setting = db.merge(AppSetting(key=key, value=payload.value))
    db.commit()
    db.refresh(setting)
    return setting
