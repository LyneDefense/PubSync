from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.article import Article
from app.models.common import utc_now
from app.models.tenant import Tenant


class TaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    succeeded = "succeeded"
    failed = "failed"


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
