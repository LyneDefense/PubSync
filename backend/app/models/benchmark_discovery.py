import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.blogger import BloggerProfile
from app.models.common import utc_now
from app.models.task import OperationTask
from app.models.tenant import Tenant
from app.database import Base


class BenchmarkDiscoverySession(Base):
    """泛搜索（找对标）的一次「发现会话」——多步状态机的持久化载体。

    流程: S1 意图 → S2 确认方向 → S3 召回候选 → S4 下一步网关(循环) → S5 完成。
    等待用户输入发生在 HTTP 请求边界(服务端不挂进程);空闲超过 expires_at 由清理任务标 expired。
    各 *_json 存结构化状态;stage/status/round 为标量便于查询与转场。
    """

    __tablename__ = "benchmark_discovery_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs")
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="intent")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    my_account_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    # 结构化状态(JSON 文本)
    intent_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    directions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    seeds_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    candidates_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    seen_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    basket_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    message: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    my_account: Mapped[BloggerProfile | None] = relationship()
    task: Mapped[OperationTask | None] = relationship()
    tenant: Mapped[Tenant] = relationship()

    def _load(self, raw: str, default):
        try:
            data = json.loads(raw or "null")
        except (json.JSONDecodeError, TypeError):
            return default
        return data if data is not None else default

    @property
    def intent(self) -> dict:
        d = self._load(self.intent_json, {})
        return d if isinstance(d, dict) else {}

    @property
    def directions(self) -> list[dict]:
        d = self._load(self.directions_json, [])
        return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []

    @property
    def seeds(self) -> list[dict]:
        d = self._load(self.seeds_json, [])
        return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []

    @property
    def candidates(self) -> list[dict]:
        d = self._load(self.candidates_json, [])
        return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []

    @property
    def seen(self) -> list[str]:
        d = self._load(self.seen_json, [])
        return [str(x) for x in d] if isinstance(d, list) else []

    @property
    def basket(self) -> list[dict]:
        d = self._load(self.basket_json, [])
        return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []
