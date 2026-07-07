"""退役泛搜索/找相似「发现会话」:删除 benchmark_discovery_sessions 表。

发现会话(多步状态机)整套早已下线,无端点/前端/清理任务在用。无外键指向本表,可干净删除。
downgrade 重建空表(仅为可逆,不恢复数据)。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0024_drop_benchmark_discovery"
down_revision = "0023_drop_benchmark_recomm_runs"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("benchmark_discovery_sessions"):
        op.drop_table("benchmark_discovery_sessions")


def downgrade() -> None:
    if not _has_table("benchmark_discovery_sessions"):
        op.create_table(
            "benchmark_discovery_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("platform", sa.String(length=30), nullable=False, server_default="xhs"),
            sa.Column("stage", sa.String(length=30), nullable=False, server_default="intent"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active", index=True),
            sa.Column("round", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("my_account_id", sa.Integer(), sa.ForeignKey("blogger_profiles.id"), nullable=True),
            sa.Column("task_id", sa.String(length=36), sa.ForeignKey("operation_tasks.id"), nullable=True, index=True),
            sa.Column("intent_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("directions_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("seeds_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("candidates_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("seen_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("basket_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("message", sa.String(length=400), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
