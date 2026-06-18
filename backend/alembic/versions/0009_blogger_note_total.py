"""博主笔记总数:blogger_profiles.note_total。

在 0001 baseline 之上的增量迁移(给既有表加列)。做列存在性判断,保证 create_all 与 stamp 升级两条路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_blogger_note_total"
down_revision = "0008_post_lifecycle"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "note_total" not in _columns("blogger_profiles"):
        op.add_column("blogger_profiles", sa.Column("note_total", sa.Integer(), nullable=True))


def downgrade() -> None:
    if "note_total" in _columns("blogger_profiles"):
        op.drop_column("blogger_profiles", "note_total")
