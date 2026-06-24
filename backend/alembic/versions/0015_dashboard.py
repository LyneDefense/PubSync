"""效果看板:xhs_publish_packages 加 my_account_id/published_at;新增 account_metric_snapshots。

在 0014 之上的增量迁移。加列前判存在、建表前判存在,幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_dashboard"
down_revision = "0014_skill_training_run"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if _has_table("xhs_publish_packages"):
        cols = _columns("xhs_publish_packages")
        if "my_account_id" not in cols:
            op.add_column(
                "xhs_publish_packages",
                sa.Column("my_account_id", sa.Integer(), sa.ForeignKey("blogger_profiles.id"), nullable=True, index=True),
            )
        if "published_at" not in cols:
            op.add_column(
                "xhs_publish_packages",
                sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            )

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


def downgrade() -> None:
    if _has_table("account_metric_snapshots"):
        op.drop_table("account_metric_snapshots")
    if _has_table("xhs_publish_packages"):
        cols = _columns("xhs_publish_packages")
        if "published_at" in cols:
            op.drop_column("xhs_publish_packages", "published_at")
        if "my_account_id" in cols:
            op.drop_column("xhs_publish_packages", "my_account_id")
