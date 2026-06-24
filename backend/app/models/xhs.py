from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    # 这篇创作给我的哪个账号用(account_type=mine);可空(用户未绑/还没添加自己的账号)。
    my_account_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=True, index=True)
    # 用户反馈「我已发布」的时间;非空即视为已发布。
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship(foreign_keys=[blogger_id])
    skill: Mapped[BloggerSkill] = relationship()
    my_account: Mapped[BloggerProfile | None] = relationship(foreign_keys=[my_account_id])
    tenant: Mapped[Tenant] = relationship()


class AccountMetricSnapshot(Base):
    """「我的账号」每日指标快照,用于画涨粉/互动趋势(BloggerProfile 只存当前值会被覆盖)。

    每账号每天一行(account_id + captured_on 唯一);同日重跑覆盖(幂等 upsert)。
    """

    __tablename__ = "account_metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    captured_on: Mapped[date] = mapped_column(Date, nullable=False)
    follower_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (UniqueConstraint("account_id", "captured_on", name="uq_account_metric_day"),)

    account: Mapped[BloggerProfile] = relationship()
    tenant: Mapped[Tenant] = relationship()
