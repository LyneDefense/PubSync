"""退役 Skill 优化模块:删除 skill_training_runs 表。

Skill 优化(SkillOpt 训练)PoC 结论为负(训练无法超过种子),整模块退役。
无任何外键指向本表,可干净删除。downgrade 重建空表(仅为可逆,不恢复数据)。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0021_drop_skill_training_runs"
down_revision = "0020_dossier_quality"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("skill_training_runs"):
        op.drop_table("skill_training_runs")


def downgrade() -> None:
    if not _has_table("skill_training_runs"):
        op.create_table(
            "skill_training_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("blogger_id", sa.Integer(), sa.ForeignKey("blogger_profiles.id"), nullable=False, index=True),
            sa.Column("base_skill_id", sa.Integer(), sa.ForeignKey("blogger_skills.id"), nullable=True, index=True),
            sa.Column("result_skill_id", sa.Integer(), sa.ForeignKey("blogger_skills.id"), nullable=True, index=True),
            sa.Column("task_id", sa.String(length=36), sa.ForeignKey("operation_tasks.id"), nullable=True, index=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
            sa.Column("modality", sa.String(length=30), nullable=False, server_default=""),
            sa.Column("before_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("after_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("before_gap", sa.Float(), nullable=False, server_default="0"),
            sa.Column("after_gap", sa.Float(), nullable=False, server_default="0"),
            sa.Column("delta", sa.Float(), nullable=False, server_default="0"),
            sa.Column("verdict", sa.String(length=20), nullable=False, server_default=""),
            sa.Column("recommend_adopt", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("optimized_skill_markdown", sa.Text(), nullable=False, server_default=""),
            sa.Column("report_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
