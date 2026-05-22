from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ArticleStatus, SourceStatus, TaskStatus


class NewsItemRead(BaseModel):
    id: int
    title: str
    source: str
    url: str
    published_at: datetime
    summary: str
    category: str
    region: str
    importance_score: int
    selected: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewsItemUpdate(BaseModel):
    selected: bool | None = None
    summary: str | None = Field(default=None, min_length=1)
    importance_score: int | None = Field(default=None, ge=0, le=100)


class ArticleRead(BaseModel):
    id: int
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


class OperationTaskRead(BaseModel):
    id: str
    task_type: str
    status: TaskStatus
    message: str
    article_id: int | None
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


class SettingRead(BaseModel):
    key: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class SettingUpdate(BaseModel):
    value: str


class NewsSourceRead(BaseModel):
    id: int
    name: str
    url: str
    status: SourceStatus

    model_config = ConfigDict(from_attributes=True)
