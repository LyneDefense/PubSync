from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.blogger import BloggerProfile, BloggerSkill
from app.models.common import utc_now
from app.models.tenant import Tenant


class AccountAuditRun(Base):
    """账号体检/对标:把用户自己账号的内容,与该平台蒸馏出的对标博主做对比,产出结论。"""

    __tablename__ = "account_audit_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs", index=True)
    # 诊断类型:benchmark=对标诊断(我的账号 vs 对标账号),self=诊断我的(只看我的账号)。
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="benchmark", index=True)
    my_blogger_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=True, index=True)
    benchmark_blogger_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=True, index=True)
    benchmark_skill_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_skills.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    input_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()
    # 两个外键都指向 blogger_profiles,需显式指明各自的 foreign_keys 以消除歧义。
    my_blogger: Mapped[BloggerProfile | None] = relationship(foreign_keys=[my_blogger_id])
    benchmark_blogger: Mapped[BloggerProfile | None] = relationship(foreign_keys=[benchmark_blogger_id])
    benchmark_skill: Mapped[BloggerSkill | None] = relationship()
