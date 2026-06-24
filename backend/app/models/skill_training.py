import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.blogger import BloggerProfile, BloggerSkill
from app.models.common import utc_now
from app.models.task import OperationTask
from app.models.tenant import Tenant


class SkillTrainingRun(Base):
    """一次 Skill 优化(训练)运行。

    base_skill = 优化起点(博主当前 active skill);result_skill = 采纳后新建的版本(未采纳为 NULL)。
    report_json 存详情:锚点、数据计数、每轮门控、优化器改了什么(changelog)、前后样例三栏。
    verdict/recommend_adopt 用于"即使没提升也明确建议用户不要采纳"。
    """

    __tablename__ = "skill_training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    base_skill_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_skills.id"), nullable=True, index=True)
    result_skill_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_skills.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    modality: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    # 风格相似度(0-100)与 gap_closed(%)的前后对比。
    before_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    after_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    before_gap: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    after_gap: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    delta: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False, default="", server_default="")
    recommend_adopt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    optimized_skill_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    base_skill: Mapped[BloggerSkill | None] = relationship(foreign_keys=[base_skill_id])
    result_skill: Mapped[BloggerSkill | None] = relationship(foreign_keys=[result_skill_id])
    task: Mapped[OperationTask | None] = relationship()
    tenant: Mapped[Tenant] = relationship()

    @property
    def report(self) -> dict:
        try:
            data = json.loads(self.report_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}
