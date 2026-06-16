"""system_config:运行时配置覆盖表(全局,非租户级)。

在 0001 baseline 之上的增量迁移(新增单表)。

注意:0001 baseline 用 ``Base.metadata.create_all`` 基于「当前」ORM 建全部表,
全新库会在 0001 就把本表建好;而线上既有库停在 0001(那时还没有本表),只会跑本迁移。
因此 upgrade/downgrade 都做存在性判断,保证两种路径都安全幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_system_config"
down_revision = "0002_account_audit_runs"
branch_labels = None
depends_on = None

TABLE = "system_config"


def _has_table() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def upgrade() -> None:
    if _has_table():  # 全新库:0001 的 create_all 已建好,跳过。
        return
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    if not _has_table():
        return
    op.drop_table("system_config")
