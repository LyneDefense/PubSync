"""退役效果看板:删除 account_metric_snapshots 表。

效果看板(成长分析盘)退役,「我的账号」每日指标快照不再采集。
无外键指向本表,可干净删除。downgrade 重建空表(仅为可逆,不恢复数据)。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0022_drop_account_metrics"
down_revision = "0021_drop_skill_training_runs"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("account_metric_snapshots"):
        op.drop_table("account_metric_snapshots")


def downgrade() -> None:
    if not _has_table("account_metric_snapshots"):
        op.create_table(
            "account_metric_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("account_id", sa.Integer(), sa.ForeignKey("blogger_profiles.id"), nullable=False, index=True),
            sa.Column("captured_on", sa.Date(), nullable=False),
            sa.Column("follower_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("note_total", sa.Integer(), nullable=True),
            sa.Column("total_interactions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("account_id", "captured_on", name="uq_account_metric_day"),
        )
