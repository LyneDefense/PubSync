from pydantic import BaseModel, ConfigDict, Field


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
