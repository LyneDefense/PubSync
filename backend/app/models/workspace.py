from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import utc_now
from app.models.tenant import Tenant


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


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()
