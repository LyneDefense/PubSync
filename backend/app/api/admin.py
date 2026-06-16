import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, settings
from app.database import get_db
from app.models import Tenant, TenantStatus, User
from app.schemas import AdminTenantRead, AdminUserCreate, AdminUserRead, PasswordReset
from app.services.auth_service import get_user_by_username, hash_password
from app.services.tenant_service import ensure_tenant_defaults

router = APIRouter()


def normalize_tenant_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_").lower()
    return slug[:80] or "workspace"


@router.get("/admin/users", response_model=list[AdminUserRead])
def admin_list_users_endpoint(
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())))


@router.post("/admin/users", response_model=AdminUserRead)
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


@router.get("/admin/tenants", response_model=list[AdminTenantRead])
def admin_list_tenants_endpoint(
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Tenant]:
    return list(db.scalars(select(Tenant).order_by(Tenant.created_at.desc(), Tenant.id.desc())))


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    return user


@router.post("/admin/users/{user_id}/disable", response_model=AdminUserRead)
def admin_disable_user_endpoint(
    user_id: int,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = _get_user_or_404(db, user_id)
    user.status = "disabled"
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/users/{user_id}/enable", response_model=AdminUserRead)
def admin_enable_user_endpoint(
    user_id: int,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = _get_user_or_404(db, user_id)
    user.status = "active"
    db.commit()
    db.refresh(user)
    return user


@router.post("/admin/users/{user_id}/reset-password", response_model=AdminUserRead)
def admin_reset_password_endpoint(
    user_id: int,
    payload: PasswordReset,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = _get_user_or_404(db, user_id)
    user.password_hash = hash_password(payload.password, settings)
    db.commit()
    db.refresh(user)
    return user
