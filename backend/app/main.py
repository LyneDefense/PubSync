from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, create_db_and_tables, get_db
from app.models import AppSetting, Article, NewsItem, OperationTask, TaskStatus
from app.schemas import (
    ArticleRead,
    ArticleUpdate,
    DashboardRead,
    NewsItemRead,
    NewsItemUpdate,
    OperationTaskRead,
    SettingRead,
    SettingUpdate,
)
from app.services.ai_service import AIServiceError
from app.services.article_service import generate_article_from_selected_news, update_article
from app.services.auth_service import create_token, verify_credentials, verify_token
from app.services.news_service import fetch_latest_news, list_news
from app.services.wechat_service import WeChatAPIError, send_article_to_wechat_draft


settings = get_settings()
Path(settings.static_dir).mkdir(parents=True, exist_ok=True)
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def run_article_generation_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.get(OperationTask, task_id)
        if not task:
            return

        task.status = TaskStatus.running
        task.message = "正在生成文章，可能需要数分钟"
        task.error_message = None
        db.commit()

        article = generate_article_from_selected_news(db)
        task.status = TaskStatus.succeeded
        task.message = "文章生成完成"
        task.article_id = article.id
        task.error_message = None
        db.commit()
    except (ValueError, AIServiceError) as exc:
        db.rollback()
        task = db.get(OperationTask, task_id)
        if task:
            task.status = TaskStatus.failed
            task.message = "文章生成失败"
            task.error_message = str(exc)
            db.commit()
    except Exception as exc:
        db.rollback()
        task = db.get(OperationTask, task_id)
        if task:
            task.status = TaskStatus.failed
            task.message = "文章生成失败"
            task.error_message = f"{type(exc).__name__}: {exc}"
            db.commit()
        raise
    finally:
        db.close()


def run_news_fetch_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.get(OperationTask, task_id)
        if not task:
            return

        task.status = TaskStatus.running
        task.message = "正在抓取新闻并进行 AI 筛选"
        task.error_message = None
        db.commit()

        created_items = fetch_latest_news(db)
        task.status = TaskStatus.succeeded
        task.message = f"新闻抓取完成，新增 {len(created_items)} 条"
        task.error_message = None
        db.commit()
    except AIServiceError as exc:
        db.rollback()
        task = db.get(OperationTask, task_id)
        if task:
            task.status = TaskStatus.failed
            task.message = "新闻抓取失败"
            task.error_message = str(exc)
            db.commit()
    except Exception as exc:
        db.rollback()
        task = db.get(OperationTask, task_id)
        if task:
            task.status = TaskStatus.failed
            task.message = "新闻抓取失败"
            task.error_message = f"{type(exc).__name__}: {exc}"
            db.commit()
        raise
    finally:
        db.close()


def scheduled_news_fetch() -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        fetch_latest_news(db)
        article = generate_article_from_selected_news(db)
        if settings.auto_send_wechat_draft:
            send_article_to_wechat_draft(db, article)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    scheduler.add_job(
        scheduled_news_fetch,
        "cron",
        hour=settings.publish_time_hour,
        minute=settings.publish_time_minute,
        id="daily_news_fetch",
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
    return LoginResponse(access_token=create_token(settings))


@app.get("/dashboard", response_model=DashboardRead)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardRead:
    news_count = db.scalar(select(func.count()).select_from(NewsItem)) or 0
    selected_count = db.scalar(select(func.count()).select_from(NewsItem).where(NewsItem.selected.is_(True))) or 0
    latest_article = db.scalar(select(Article).order_by(Article.created_at.desc()).limit(1))
    last_fetch_at = db.get(AppSetting, "last_fetch_at")
    return DashboardRead(
        news_count=news_count,
        selected_count=selected_count,
        latest_article=latest_article,
        last_fetch_at=last_fetch_at.value if last_fetch_at else None,
        scheduled_publish_time=f"{settings.publish_time_hour:02d}:{settings.publish_time_minute:02d}",
    )


@app.post("/news/fetch", response_model=OperationTaskRead)
def fetch_news_endpoint(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> OperationTask:
    task = OperationTask(
        id=str(uuid4()),
        task_type="news_fetch",
        status=TaskStatus.queued,
        message="已加入后台抓取任务",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    background_tasks.add_task(run_news_fetch_task, task.id)
    return task


@app.get("/news", response_model=list[NewsItemRead])
def list_news_endpoint(db: Session = Depends(get_db)) -> list[NewsItem]:
    return list_news(db)


@app.patch("/news/{news_id}", response_model=NewsItemRead)
def update_news_endpoint(news_id: int, payload: NewsItemUpdate, db: Session = Depends(get_db)) -> NewsItem:
    news = db.get(NewsItem, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="News item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(news, key, value)
    db.commit()
    db.refresh(news)
    return news


@app.post("/articles/generate", response_model=OperationTaskRead)
def generate_article_endpoint(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> OperationTask:
    task = OperationTask(
        id=str(uuid4()),
        task_type="article_generation",
        status=TaskStatus.queued,
        message="已加入后台生成任务",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    background_tasks.add_task(run_article_generation_task, task.id)
    return task


@app.get("/tasks/{task_id}", response_model=OperationTaskRead)
def get_task_endpoint(task_id: str, db: Session = Depends(get_db)) -> OperationTask:
    task = db.get(OperationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/articles/latest", response_model=ArticleRead | None)
def latest_article_endpoint(db: Session = Depends(get_db)) -> Article | None:
    return db.scalar(select(Article).order_by(Article.created_at.desc()).limit(1))


@app.patch("/articles/{article_id}", response_model=ArticleRead)
def update_article_endpoint(article_id: int, payload: ArticleUpdate, db: Session = Depends(get_db)) -> Article:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return update_article(db, article, **payload.model_dump(exclude_unset=True))


@app.post("/articles/{article_id}/send-to-wechat", response_model=ArticleRead)
def send_to_wechat_endpoint(article_id: int, db: Session = Depends(get_db)) -> Article:
    article = db.get(Article, article_id)
    if not article:
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
