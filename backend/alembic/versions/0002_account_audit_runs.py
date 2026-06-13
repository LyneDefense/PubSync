"""account_audit_runs:账号体检/对标 运行记录表。

在 0001 baseline 之上的增量迁移(新增单表)。

注意:0001 baseline 用 ``Base.metadata.create_all`` 基于「当前」ORM 建全部表,
全新库会在 0001 就把本表建好;而线上既有库停在 0001(那时还没有本表),只会跑本迁移。
因此 upgrade/downgrade 都做存在性判断,保证两种路径都安全幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_account_audit_runs"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

TABLE = "account_audit_runs"


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if _has_table():  # 全新库:0001 的 create_all 已建好,跳过。
        return
    op.create_table(
        "account_audit_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False, server_default="xhs"),
        sa.Column("benchmark_blogger_id", sa.Integer(), nullable=True),
        sa.Column("benchmark_skill_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
        sa.Column("input_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("report_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["benchmark_blogger_id"], ["blogger_profiles.id"]),
        sa.ForeignKeyConstraint(["benchmark_skill_id"], ["blogger_skills.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["operation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_audit_runs_id", "account_audit_runs", ["id"])
    op.create_index("ix_account_audit_runs_tenant_id", "account_audit_runs", ["tenant_id"])
    op.create_index("ix_account_audit_runs_platform", "account_audit_runs", ["platform"])
    op.create_index("ix_account_audit_runs_benchmark_blogger_id", "account_audit_runs", ["benchmark_blogger_id"])
    op.create_index("ix_account_audit_runs_benchmark_skill_id", "account_audit_runs", ["benchmark_skill_id"])
    op.create_index("ix_account_audit_runs_task_id", "account_audit_runs", ["task_id"])


def downgrade() -> None:
    if not _has_table():
        return
    op.drop_index("ix_account_audit_runs_task_id", table_name="account_audit_runs")
    op.drop_index("ix_account_audit_runs_benchmark_skill_id", table_name="account_audit_runs")
    op.drop_index("ix_account_audit_runs_benchmark_blogger_id", table_name="account_audit_runs")
    op.drop_index("ix_account_audit_runs_platform", table_name="account_audit_runs")
    op.drop_index("ix_account_audit_runs_tenant_id", table_name="account_audit_runs")
    op.drop_index("ix_account_audit_runs_id", table_name="account_audit_runs")
    op.drop_table("account_audit_runs")
