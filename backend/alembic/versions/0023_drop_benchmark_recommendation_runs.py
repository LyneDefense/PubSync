"""退役对标发现「智能推荐 + 单博主评分」:删除 benchmark_recommendation_runs 表。

推荐/评分整套(前后端)退役,「搜索 + 采用」保留。无外键指向本表,可干净删除。
downgrade 重建空表(仅为可逆,不恢复数据)。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0023_drop_benchmark_recomm_runs"
down_revision = "0022_drop_account_metrics"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("benchmark_recommendation_runs"):
        op.drop_table("benchmark_recommendation_runs")


def downgrade() -> None:
    if not _has_table("benchmark_recommendation_runs"):
        op.create_table(
            "benchmark_recommendation_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("platform", sa.String(length=30), nullable=False, server_default="xhs"),
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="recommend"),
            sa.Column("intent_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("my_account_id", sa.Integer(), sa.ForeignKey("blogger_profiles.id"), nullable=True, index=True),
            sa.Column("task_id", sa.String(length=36), sa.ForeignKey("operation_tasks.id"), nullable=True, index=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
            sa.Column("candidates_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
