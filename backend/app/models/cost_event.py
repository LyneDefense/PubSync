from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import utc_now


class CostEvent(Base):
    """费用台账:一条 = 一次可计费事件(TikHub 请求批 / 一次 LLM 文本或图像调用)。

    金额对 TikHub 是真实累计(供应商按请求计费);对 LLM 是用内置/可编辑单价 × token/图 折算的
    估算值。归属到 tenant + task 以便后台按工作空间/任务汇总。
    """

    __tablename__ = "cost_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # tikhub/openai/minimax
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # collection/distillation/text/image
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # requests / tokens / images
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="request")
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
