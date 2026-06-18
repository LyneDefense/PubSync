"""blogger_posts.missed_crawl_count:下架对账「连续 N 次完整爬取缺失」计数。

在 0010 之上的增量迁移。加列前判存在,保证 create_all 与 stamp 升级两条路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_post_missed_crawl"
down_revision = "0010_blogger_snapshot"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "missed_crawl_count" not in _columns("blogger_posts"):
        op.add_column(
            "blogger_posts",
            sa.Column("missed_crawl_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if "missed_crawl_count" in _columns("blogger_posts"):
        op.drop_column("blogger_posts", "missed_crawl_count")
