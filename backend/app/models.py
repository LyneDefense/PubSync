from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ArticleStatus(StrEnum):
    draft = "draft"
    generated = "generated"
    sent_to_wechat = "sent_to_wechat"
    failed = "failed"


class SourceStatus(StrEnum):
    active = "active"
    muted = "muted"


class TaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    succeeded = "succeeded"
    failed = "failed"


class TenantStatus(StrEnum):
    active = "active"
    disabled = "disabled"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"),
        default=TenantStatus.active,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant | None] = relationship()


class ContentProfile(Base):
    __tablename__ = "content_profiles"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    publication_name: Mapped[str] = mapped_column(String(120), nullable=False, default="AI 科技早报")
    workspace_title: Mapped[str] = mapped_column(String(120), nullable=False, default="AI 早报")
    title_prefix: Mapped[str] = mapped_column(String(120), nullable=False, default="AI科技早报 | ")
    content_domain: Mapped[str] = mapped_column(Text, nullable=False, default="AI、科技、模型、算力、企业应用")
    editor_persona: Mapped[str] = mapped_column(Text, nullable=False, default="你是严谨的 AI 科技新闻主编")
    audience: Mapped[str] = mapped_column(Text, nullable=False, default="科技从业者、产品经理、投资人与 AI 关注者")
    article_style: Mapped[str] = mapped_column(Text, nullable=False, default="信息密度高，事实准确，带行业观察")
    grouping_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="regional")
    categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    image_style: Mapped[str] = mapped_column(Text, nullable=False, default="抽象科技视觉、信息图、芯片、网络、云与模型架构")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()


class ContentGroup(Base):
    __tablename__ = "content_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "group_key", name="uq_content_groups_tenant_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    group_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    content_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="news")
    source_urls: Mapped[str] = mapped_column(Text, nullable=False, default="")
    candidate_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    article_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    article_target: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    article_max: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()


class WeChatAccount(Base):
    __tablename__ = "wechat_accounts"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    app_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    app_secret: Mapped[str] = mapped_column(Text, nullable=False, default="")
    auto_send_draft: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()


class LayoutSettings(Base):
    __tablename__ = "layout_settings"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    template_name: Mapped[str] = mapped_column(String(80), nullable=False, default="clean")
    primary_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#0f766e")
    accent_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#64748b")
    text_color: Mapped[str] = mapped_column(String(20), nullable=False, default="inherit")
    heading_color: Mapped[str] = mapped_column(String(20), nullable=False, default="inherit")
    body_font_size: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    heading_font_size: Mapped[int] = mapped_column(Integer, nullable=False, default=19)
    line_height: Mapped[str] = mapped_column(String(20), nullable=False, default="1.85")
    section_spacing: Mapped[int] = mapped_column(Integer, nullable=False, default=28)
    image_radius: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    show_group_heading: Mapped[bool] = mapped_column(default=True)
    show_source: Mapped[bool] = mapped_column(default=True)
    show_editor_note: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()


class PublishingSettings(Base):
    __tablename__ = "publishing_settings"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    daily_publish_enabled: Mapped[bool] = mapped_column(default=False)
    publish_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    publish_weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    publish_month_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    publish_time_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    publish_time_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_send_wechat_draft: Mapped[bool] = mapped_column(default=False)
    generate_article_images: Mapped[bool] = mapped_column(default=True)
    max_article_images: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    min_article_images: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    news_source_urls: Mapped[str] = mapped_column(Text, nullable=False, default="")
    news_per_source_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    news_lookback_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    max_news_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    dedup_lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    dedup_direct_similarity: Mapped[str] = mapped_column(String(20), nullable=False, default="0.82")
    dedup_review_similarity: Mapped[str] = mapped_column(String(20), nullable=False, default="0.42")
    dedup_enable_llm_review: Mapped[bool] = mapped_column(default=True)
    article_news_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    article_news_lookback_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("tenant_id", "url", name="uq_news_items_tenant_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    region: Mapped[str] = mapped_column(String(30), default="international", nullable=False)
    group_key: Mapped[str] = mapped_column(String(80), default="global", nullable=False, index=True)
    importance_score: Mapped[int] = mapped_column(Integer, default=70)
    selected: Mapped[bool] = mapped_column(default=False)
    dedup_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dedup_status: Mapped[str] = mapped_column(String(30), default="unique", nullable=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id"), nullable=True)
    dedup_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped[Tenant] = relationship()


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    intro: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(ArticleStatus, name="article_status"),
        default=ArticleStatus.draft,
        nullable=False,
    )
    wechat_draft_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    items: Mapped[list["ArticleNewsItem"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )
    tenant: Mapped[Tenant] = relationship()


class ArticleNewsItem(Base):
    __tablename__ = "article_news_items"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    news_item_id: Mapped[int] = mapped_column(ForeignKey("news_items.id"), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    article: Mapped[Article] = relationship(back_populates="items")
    news_item: Mapped[NewsItem] = relationship()
    tenant: Mapped[Tenant] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, name="source_status"),
        default=SourceStatus.active,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped[Tenant] = relationship()


class OperationTask(Base):
    __tablename__ = "operation_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"),
        default=TaskStatus.queued,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(300), nullable=False, default="已加入后台任务")
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    article: Mapped[Article | None] = relationship()
    tenant: Mapped[Tenant] = relationship()


class OperationTaskEvent(Base):
    __tablename__ = "operation_task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("operation_tasks.id"), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped[OperationTask] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerProfile(Base):
    __tablename__ = "blogger_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "homepage_url", name="uq_blogger_profiles_tenant_homepage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs")
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    niche: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_distilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()


class BloggerPost(Base):
    __tablename__ = "blogger_posts"
    __table_args__ = (UniqueConstraint("tenant_id", "blogger_id", "external_id", name="uq_blogger_posts_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs")
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="image")
    hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cover_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    media_urls_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    asr_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_required")
    asr_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    favorite_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    share_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    comments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerDistillationRun(Base):
    __tablename__ = "blogger_distillation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hot_post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_min_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_max_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    report_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    task: Mapped[OperationTask | None] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerSkill(Base):
    __tablename__ = "blogger_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("blogger_distillation_runs.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skill_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    run: Mapped[BloggerDistillationRun] = relationship()
    tenant: Mapped[Tenant] = relationship()
