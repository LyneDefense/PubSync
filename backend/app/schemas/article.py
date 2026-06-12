from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ArticleStatus


class ArticleRead(BaseModel):
    id: int
    tenant_id: int
    title: str
    intro: str
    content_html: str
    cover_image_url: str
    status: ArticleStatus
    wechat_draft_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    intro: str | None = Field(default=None, min_length=1)
    content_html: str | None = Field(default=None, min_length=1)
    cover_image_url: str | None = Field(default=None, min_length=1)


class DashboardRead(BaseModel):
    news_count: int
    selected_count: int
    latest_article: ArticleRead | None
    last_fetch_at: str | None
    scheduled_publish_time: str
