from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import TenantStatus


class TenantRead(BaseModel):
    id: int
    name: str
    slug: str
    status: TenantStatus

    model_config = ConfigDict(from_attributes=True)


class CurrentUserRead(BaseModel):
    username: str
    is_admin: bool
    tenant_id: int | None


class AdminUserRead(BaseModel):
    id: int
    username: str
    is_admin: bool
    tenant_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=6, max_length=120)
    tenant_name: str = Field(min_length=1, max_length=120)
    tenant_slug: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    is_admin: bool = False
