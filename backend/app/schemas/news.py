from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import SourceStatus


class NewsItemRead(BaseModel):
    id: int
    tenant_id: int
    title: str
    source: str
    url: str
    published_at: datetime
    summary: str
    category: str
    region: str
    group_key: str
    importance_score: int
    selected: bool
    dedup_status: str
    duplicate_of_id: int | None
    dedup_reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewsItemUpdate(BaseModel):
    selected: bool | None = None
    summary: str | None = Field(default=None, min_length=1)
    importance_score: int | None = Field(default=None, ge=0, le=100)


class NewsSourceRead(BaseModel):
    id: int
    name: str
    url: str
    status: SourceStatus

    model_config = ConfigDict(from_attributes=True)
