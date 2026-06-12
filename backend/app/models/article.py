from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import utc_now
from app.models.news import NewsItem
from app.models.tenant import Tenant


class ArticleStatus(StrEnum):
    draft = "draft"
    generated = "generated"
    sent_to_wechat = "sent_to_wechat"
    failed = "failed"


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
