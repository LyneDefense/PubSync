"""账号诊断重构:blogger_profiles.account_type + account_audit_runs.kind/my_blogger_id。

在 0001 baseline 之上的增量迁移(给既有表加列)。0001 用 ``Base.metadata.create_all`` 基于当前 ORM
建表,全新库已带新列;线上既有库缺列,只跑本迁移补列。逐列做存在性判断,保证两条路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_account_module"
down_revision = "0004_cost_events"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    blogger_cols = _columns("blogger_profiles")
    if "account_type" not in blogger_cols:
        op.add_column(
            "blogger_profiles",
            sa.Column("account_type", sa.String(length=20), nullable=False, server_default="benchmark"),
        )
        op.create_index("ix_blogger_profiles_account_type", "blogger_profiles", ["account_type"])

    audit_cols = _columns("account_audit_runs")
    if "kind" not in audit_cols:
        op.add_column(
            "account_audit_runs",
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="benchmark"),
        )
        op.create_index("ix_account_audit_runs_kind", "account_audit_runs", ["kind"])
    if "my_blogger_id" not in audit_cols:
        op.add_column("account_audit_runs", sa.Column("my_blogger_id", sa.Integer(), nullable=True))
        op.create_index("ix_account_audit_runs_my_blogger_id", "account_audit_runs", ["my_blogger_id"])
        # sqlite 不支持 ALTER TABLE ADD CONSTRAINT;FK 只在 postgres(线上)建。
        if op.get_bind().dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_account_audit_runs_my_blogger_id",
                "account_audit_runs",
                "blogger_profiles",
                ["my_blogger_id"],
                ["id"],
            )


def downgrade() -> None:
    audit_cols = _columns("account_audit_runs")
    if "my_blogger_id" in audit_cols:
        if op.get_bind().dialect.name != "sqlite":
            op.drop_constraint("fk_account_audit_runs_my_blogger_id", "account_audit_runs", type_="foreignkey")
        op.drop_index("ix_account_audit_runs_my_blogger_id", table_name="account_audit_runs")
        op.drop_column("account_audit_runs", "my_blogger_id")
    if "kind" in audit_cols:
        op.drop_index("ix_account_audit_runs_kind", table_name="account_audit_runs")
        op.drop_column("account_audit_runs", "kind")
    if "account_type" in _columns("blogger_profiles"):
        op.drop_index("ix_blogger_profiles_account_type", table_name="blogger_profiles")
        op.drop_column("blogger_profiles", "account_type")
