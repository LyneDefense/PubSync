"""Shared FastAPI dependencies and helpers used across routers."""

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Tenant
from app.services.auth_service import is_admin_user, tenant_ids_for_user, token_username
from app.services.tenant_service import get_tenant

settings = get_settings()


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


def apply_pagination(stmt, limit: int | None, offset: int):
    """Apply optional offset/limit to a select statement.

    When ``limit`` is None the statement is returned unchanged, preserving the
    original "return everything" behaviour for backward compatibility.
    """
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    return stmt


LimitQuery = Query(default=None, ge=1, le=500, description="每页条数；不传则返回全部")
OffsetQuery = Query(default=0, ge=0, description="偏移量，与 limit 搭配使用")
