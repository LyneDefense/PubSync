from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import utc_now
from app.models.task import OperationTask
from app.models.tenant import Tenant


class BloggerProfile(Base):
    __tablename__ = "blogger_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "homepage_url", name="uq_blogger_profiles_tenant_homepage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs")
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    follower_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    niche: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_favorite: Mapped[bool] = mapped_column(default=False)
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


class BloggerCollectionRun(Base):
    __tablename__ = "blogger_collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    sample_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    comments_per_post: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    asr_enabled: Mapped[bool] = mapped_column(default=False)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hot_post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_min_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_max_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    task: Mapped[OperationTask | None] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerCollectionPost(Base):
    __tablename__ = "blogger_collection_posts"
    __table_args__ = (UniqueConstraint("collection_run_id", "post_id", name="uq_blogger_collection_posts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    collection_run_id: Mapped[int] = mapped_column(ForeignKey("blogger_collection_runs.id"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("blogger_posts.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    collection_run: Mapped[BloggerCollectionRun] = relationship()
    post: Mapped[BloggerPost] = relationship()
    blogger: Mapped[BloggerProfile] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerDistillationRun(Base):
    __tablename__ = "blogger_distillation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_collection_runs.id"), nullable=True, index=True)
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
    collection_run: Mapped[BloggerCollectionRun | None] = relationship()
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
