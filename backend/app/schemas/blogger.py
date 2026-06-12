from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BloggerProfileCreate(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    external_id: str | None = Field(default=None, max_length=200)
    display_name: str = Field(min_length=1, max_length=160)
    homepage_url: str = Field(min_length=1, max_length=1000)
    avatar_url: str = Field(default="", max_length=1000)
    follower_count: int = Field(default=0, ge=0)
    niche: str = Field(default="", max_length=160)
    description: str = ""


class BloggerProfileUpdate(BaseModel):
    external_id: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    homepage_url: str | None = Field(default=None, min_length=1, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=1000)
    follower_count: int | None = Field(default=None, ge=0)
    niche: str | None = Field(default=None, max_length=160)
    description: str | None = None


class BloggerFavoriteUpdate(BaseModel):
    is_favorite: bool


class BloggerProfileRead(BaseModel):
    id: int
    tenant_id: int
    platform: str
    external_id: str | None
    display_name: str
    homepage_url: str
    avatar_url: str
    follower_count: int
    niche: str
    description: str
    is_favorite: bool
    sample_count: int
    last_distilled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerSearchResultRead(BaseModel):
    platform: str
    external_id: str
    display_name: str
    homepage_url: str
    avatar_url: str
    description: str
    follower_count: int
    raw: dict


class BloggerDistillRequest(BaseModel):
    collection_run_id: int


class BloggerCollectRequest(BaseModel):
    sample_limit: int = Field(default=50, ge=5, le=200)
    comments_per_post: int = Field(default=20, ge=0, le=100)
    asr_enabled: bool = False


class BloggerPostRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    platform: str
    external_id: str
    url: str
    title: str
    body_text: str
    content_type: str
    hashtags_json: str
    cover_url: str
    media_urls_json: str
    transcript_text: str
    asr_status: str
    asr_error: str
    published_at: datetime | None
    like_count: int
    favorite_count: int
    comment_count: int
    share_count: int
    score: float
    comments_json: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerCollectionRunRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    task_id: str | None
    status: str
    sample_limit: int
    comments_per_post: int
    asr_enabled: bool
    post_count: int
    hot_post_count: int
    comment_count: int
    tikhub_request_count: int
    tikhub_estimated_cost_usd: float
    tikhub_cost_min_usd: float
    tikhub_cost_max_usd: float
    summary_json: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerDistillationRunRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    collection_run_id: int | None
    task_id: str | None
    status: str
    sample_count: int
    hot_post_count: int
    comment_count: int
    tikhub_request_count: int
    tikhub_estimated_cost_usd: float
    tikhub_cost_min_usd: float
    tikhub_cost_max_usd: float
    report_json: str
    report_html: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerSkillRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    run_id: int
    name: str
    description: str
    skill_markdown: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
