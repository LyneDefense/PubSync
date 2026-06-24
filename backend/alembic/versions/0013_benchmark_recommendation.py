"""对标博主搜寻:benchmark_recommendation_runs 表(智能推荐 / 单博主评分的运行记录)。

在 0012 之上的增量迁移。建表前判存在,保证 create_all 与 stamp 升级两条路径都幂等。
BloggerPost.status 的 'preview' 态(深看抓详情缓存)只是新增的取值,沿用既有列,无需 DDL 改动。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_benchmark_recommendation"
down_revision = "0012_post_note_key"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
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


def downgrade() -> None:
    if _has_table("benchmark_recommendation_runs"):
        op.drop_table("benchmark_recommendation_runs")
