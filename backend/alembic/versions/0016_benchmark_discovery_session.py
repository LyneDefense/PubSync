"""泛搜索（找对标）发现会话: benchmark_discovery_sessions 表。

在 0015 之上的增量迁移。建表前判存在,幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016_benchmark_discovery_session"
down_revision = "0015_dashboard"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("benchmark_discovery_sessions"):
        return
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


def downgrade() -> None:
    if _has_table("benchmark_discovery_sessions"):
        op.drop_table("benchmark_discovery_sessions")
