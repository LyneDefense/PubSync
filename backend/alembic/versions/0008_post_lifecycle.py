"""笔记生命周期:blogger_posts.status + last_seen_at(下架对账用)。

在 0001 baseline 之上的增量迁移(给既有表加列)。逐列做存在性判断,保证 create_all 与 stamp 升级两条路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_post_lifecycle"
down_revision = "0007_content_subtype"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    cols = _columns("blogger_posts")
    if "status" not in cols:
        op.add_column(
            "blogger_posts",
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        )
        op.create_index("ix_blogger_posts_status", "blogger_posts", ["status"])
    if "last_seen_at" not in cols:
        op.add_column("blogger_posts", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    cols = _columns("blogger_posts")
    if "last_seen_at" in cols:
        op.drop_column("blogger_posts", "last_seen_at")
    if "status" in cols:
        op.drop_index("ix_blogger_posts_status", table_name="blogger_posts")
        op.drop_column("blogger_posts", "status")
