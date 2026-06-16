"""cost_events:费用台账(TikHub + 大模型)。

在 0001 baseline 之上的增量迁移(新增单表)。0001 用 ``Base.metadata.create_all`` 建全部表,
全新库会在 0001 就建好本表;线上既有库停在 0001(那时还没有本表),只会跑本迁移。
因此 upgrade/downgrade 都做存在性判断,保证两种路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_cost_events"
down_revision = "0003_system_config"
branch_labels = None
depends_on = None

TABLE = "cost_events"


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if _has_table():
        return
    op.create_table(
        "cost_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="request"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["operation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cost_events_id", "cost_events", ["id"])
    op.create_index("ix_cost_events_created_at", "cost_events", ["created_at"])
    op.create_index("ix_cost_events_tenant_id", "cost_events", ["tenant_id"])
    op.create_index("ix_cost_events_task_id", "cost_events", ["task_id"])
    op.create_index("ix_cost_events_provider", "cost_events", ["provider"])


def downgrade() -> None:
    if not _has_table():
        return
    op.drop_index("ix_cost_events_provider", table_name="cost_events")
    op.drop_index("ix_cost_events_task_id", table_name="cost_events")
    op.drop_index("ix_cost_events_tenant_id", table_name="cost_events")
    op.drop_index("ix_cost_events_created_at", table_name="cost_events")
    op.drop_index("ix_cost_events_id", table_name="cost_events")
    op.drop_table("cost_events")
