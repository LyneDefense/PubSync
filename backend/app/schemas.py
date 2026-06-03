from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ArticleStatus, SourceStatus, TaskStatus, TenantStatus


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


class ContentProfileRead(BaseModel):
    tenant_id: int
    publication_name: str
    workspace_title: str
    title_prefix: str
    content_domain: str
    editor_persona: str
    audience: str
    article_style: str
    grouping_mode: str
    categories_json: str
    image_style: str

    model_config = ConfigDict(from_attributes=True)


class ContentProfileUpdate(BaseModel):
    publication_name: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_title: str | None = Field(default=None, min_length=1, max_length=120)
    title_prefix: str | None = Field(default=None, min_length=1, max_length=120)
    content_domain: str | None = Field(default=None, min_length=1)
    editor_persona: str | None = Field(default=None, min_length=1)
    audience: str | None = Field(default=None, min_length=1)
    article_style: str | None = Field(default=None, min_length=1)
    grouping_mode: str | None = Field(default=None, pattern="^(regional|none)$")
    categories_json: str | None = Field(default=None, min_length=1)
    image_style: str | None = Field(default=None, min_length=1)


class ContentGroupRead(BaseModel):
    id: int
    tenant_id: int
    group_key: str
    name: str
    content_mode: str
    source_urls: str
    candidate_limit: int
    article_min: int
    article_target: int
    article_max: int
    position: int
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class ContentGroupUpdate(BaseModel):
    group_key: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    content_mode: str | None = Field(default=None, pattern="^(news|knowledge|analysis)$")
    source_urls: str | None = ""
    candidate_limit: int | None = Field(default=None, ge=0, le=300)
    article_min: int | None = Field(default=None, ge=0, le=50)
    article_target: int | None = Field(default=None, ge=0, le=50)
    article_max: int | None = Field(default=None, ge=0, le=50)
    position: int | None = Field(default=None, ge=0, le=50)
    enabled: bool | None = None


class WeChatAccountRead(BaseModel):
    tenant_id: int
    app_id: str
    app_secret_configured: bool


class WeChatAccountUpdate(BaseModel):
    app_id: str | None = Field(default=None, max_length=120)
    app_secret: str | None = None


class LayoutSettingsRead(BaseModel):
    tenant_id: int
    template_name: str
    primary_color: str
    accent_color: str
    text_color: str
    heading_color: str
    body_font_size: int
    heading_font_size: int
    line_height: str
    section_spacing: int
    image_radius: int
    show_group_heading: bool
    show_source: bool
    show_editor_note: bool

    model_config = ConfigDict(from_attributes=True)


class LayoutSettingsUpdate(BaseModel):
    template_name: str | None = Field(default=None, min_length=1, max_length=80)
    primary_color: str | None = Field(default=None, min_length=3, max_length=20)
    accent_color: str | None = Field(default=None, min_length=3, max_length=20)
    text_color: str | None = Field(default=None, min_length=3, max_length=20)
    heading_color: str | None = Field(default=None, min_length=3, max_length=20)
    body_font_size: int | None = Field(default=None, ge=12, le=20)
    heading_font_size: int | None = Field(default=None, ge=14, le=26)
    line_height: str | None = Field(default=None, min_length=1, max_length=20)
    section_spacing: int | None = Field(default=None, ge=12, le=48)
    image_radius: int | None = Field(default=None, ge=0, le=24)
    show_group_heading: bool | None = None
    show_source: bool | None = None
    show_editor_note: bool | None = None


class PublishingSettingsRead(BaseModel):
    tenant_id: int
    daily_publish_enabled: bool
    publish_frequency: str
    publish_weekday: int
    publish_month_day: int
    publish_time_hour: int
    publish_time_minute: int
    auto_send_wechat_draft: bool
    generate_article_images: bool
    max_article_images: int
    min_article_images: int
    news_source_urls: str
    news_per_source_limit: int
    news_lookback_hours: int
    max_news_candidates: int
    dedup_lookback_days: int
    dedup_direct_similarity: str
    dedup_review_similarity: str
    dedup_enable_llm_review: bool
    article_news_limit: int
    article_news_lookback_hours: int

    model_config = ConfigDict(from_attributes=True)


class PublishingSettingsUpdate(BaseModel):
    daily_publish_enabled: bool | None = None
    publish_frequency: str | None = Field(default=None, pattern="^(daily|weekly|monthly)$")
    publish_weekday: int | None = Field(default=None, ge=1, le=7)
    publish_month_day: int | None = Field(default=None, ge=1, le=31)
    publish_time_hour: int | None = Field(default=None, ge=0, le=23)
    publish_time_minute: int | None = Field(default=None, ge=0, le=59)
    auto_send_wechat_draft: bool | None = None
    generate_article_images: bool | None = None
    max_article_images: int | None = Field(default=None, ge=0, le=10)
    min_article_images: int | None = Field(default=None, ge=0, le=10)
    news_source_urls: str | None = None
    news_per_source_limit: int | None = Field(default=None, ge=1, le=50)
    news_lookback_hours: int | None = Field(default=None, ge=1, le=168)
    max_news_candidates: int | None = Field(default=None, ge=1, le=300)
    dedup_lookback_days: int | None = Field(default=None, ge=1, le=30)
    dedup_direct_similarity: str | None = Field(default=None, min_length=1, max_length=20)
    dedup_review_similarity: str | None = Field(default=None, min_length=1, max_length=20)
    dedup_enable_llm_review: bool | None = None
    article_news_limit: int | None = Field(default=None, ge=1, le=50)
    article_news_lookback_hours: int | None = Field(default=None, ge=1, le=168)


class WorkspaceConfigRead(BaseModel):
    profile: ContentProfileRead
    wechat: WeChatAccountRead
    layout: LayoutSettingsRead
    publishing: PublishingSettingsRead
    content_groups: list[ContentGroupRead]


class WorkspaceConfigUpdate(BaseModel):
    profile: ContentProfileUpdate | None = None
    wechat: WeChatAccountUpdate | None = None
    layout: LayoutSettingsUpdate | None = None
    publishing: PublishingSettingsUpdate | None = None
    content_groups: list[ContentGroupUpdate] | None = None


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


class OperationTaskRead(BaseModel):
    id: str
    tenant_id: int
    task_type: str
    status: TaskStatus
    message: str
    article_id: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationTaskEventRead(BaseModel):
    id: int
    tenant_id: int
    task_id: str
    step_name: str
    status: str
    message: str
    payload_json: str | None
    created_at: datetime

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


class BloggerProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    homepage_url: str = Field(min_length=1, max_length=1000)
    niche: str = Field(default="", max_length=160)
    description: str = ""


class BloggerProfileRead(BaseModel):
    id: int
    tenant_id: int
    platform: str
    display_name: str
    homepage_url: str
    niche: str
    description: str
    sample_count: int
    last_distilled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
