"""蒸馏选材快照:blogger_snapshots 表 + blogger_distillation_runs.snapshot_id/selection_json。

在 0001 baseline 之上的增量迁移。建表前判存在;加列前判存在,保证 create_all 与 stamp 升级两条路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_blogger_snapshot"
down_revision = "0009_blogger_note_total"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_table("blogger_snapshots"):
        op.create_table(
            "blogger_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("blogger_id", sa.Integer(), sa.ForeignKey("blogger_profiles.id"), nullable=False, index=True),
            sa.Column("name", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("post_ids_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    run_cols = _columns("blogger_distillation_runs")
    if "snapshot_id" not in run_cols:
        op.add_column("blogger_distillation_runs", sa.Column("snapshot_id", sa.Integer(), nullable=True))
        op.create_index("ix_blogger_distillation_runs_snapshot_id", "blogger_distillation_runs", ["snapshot_id"])
        if op.get_bind().dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_blogger_distillation_runs_snapshot_id",
                "blogger_distillation_runs",
                "blogger_snapshots",
                ["snapshot_id"],
                ["id"],
            )
    if "selection_json" not in run_cols:
        op.add_column(
            "blogger_distillation_runs",
            sa.Column("selection_json", sa.Text(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    run_cols = _columns("blogger_distillation_runs")
    if "selection_json" in run_cols:
        op.drop_column("blogger_distillation_runs", "selection_json")
    if "snapshot_id" in run_cols:
        if op.get_bind().dialect.name != "sqlite":
            op.drop_constraint("fk_blogger_distillation_runs_snapshot_id", "blogger_distillation_runs", type_="foreignkey")
        op.drop_index("ix_blogger_distillation_runs_snapshot_id", table_name="blogger_distillation_runs")
        op.drop_column("blogger_distillation_runs", "snapshot_id")
    if _has_table("blogger_snapshots"):
        op.drop_table("blogger_snapshots")
