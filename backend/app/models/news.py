from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import utc_now
from app.models.tenant import Tenant


class SourceStatus(StrEnum):
    active = "active"
    muted = "muted"


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
