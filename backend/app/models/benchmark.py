import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.blogger import BloggerProfile
from app.models.common import utc_now
from app.models.task import OperationTask
from app.models.tenant import Tenant


class BenchmarkRecommendationRun(Base):
    """对标博主搜寻的一次「智能推荐 / 单博主评分」运行。

    intent_json 存用户意图(领域/受众/目标/形式);candidates_json 存候选 + 各项评分 + 依据。
    kind=recommend(候选池批量) / evaluate(单博主)。my_account_id 可选,绑了"我的账号"则评估更准。
    """

    __tablename__ = "benchmark_recommendation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs")
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="recommend")
    intent_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    my_account_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    candidates_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    my_account: Mapped[BloggerProfile | None] = relationship()
    task: Mapped[OperationTask | None] = relationship()
    tenant: Mapped[Tenant] = relationship()

    @property
    def intent(self) -> dict:
        try:
            data = json.loads(self.intent_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    @property
    def candidates(self) -> list[dict]:
        try:
            data = json.loads(self.candidates_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []
        return [c for c in data if isinstance(c, dict)]
