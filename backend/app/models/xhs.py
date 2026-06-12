from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.blogger import BloggerProfile, BloggerSkill
from app.models.common import utc_now
from app.models.tenant import Tenant


class XhsPublishPackage(Base):
    __tablename__ = "xhs_publish_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("blogger_skills.id"), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    target_audience: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    content_goal: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    keywords: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    image_count_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="auto")
    requested_image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cover_text: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    image_plan_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    image_urls_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    script_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    skill: Mapped[BloggerSkill] = relationship()
    tenant: Mapped[Tenant] = relationship()
