from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_username, settings
from app.database import get_db
from app.schemas import CurrentUserRead
from app.services.auth_service import (
    create_token,
    get_user_by_username,
    is_admin_user,
    tenant_ids_for_user,
    verify_credentials,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    if not verify_credentials(payload.username, payload.password, settings, db):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(access_token=create_token(settings, payload.username))


@router.get("/auth/me", response_model=CurrentUserRead)
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
