from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    admin,
    articles,
    auth,
    bloggers,
    dashboard,
    health,
    news,
    tasks,
    tenants,
    workspace,
    xhs,
)
from app.api import settings as settings_routes
from app.config import get_settings
from app.database import create_db_and_tables
from app.logging_config import configure_logging
from app.services.auth_service import verify_token
from app.services.task_service import scheduled_workspace_publish

settings = get_settings()
Path(settings.static_dir).mkdir(parents=True, exist_ok=True)
configure_logging()
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


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


# Routers are registered in this order; literal paths (e.g. /bloggers/search) are
# defined before their {param} siblings inside each router so matching is stable.
for module in (
    health,
    auth,
    tenants,
    admin,
    workspace,
    dashboard,
    news,
    articles,
    bloggers,
    xhs,
    tasks,
    settings_routes,
):
    app.include_router(module.router)
