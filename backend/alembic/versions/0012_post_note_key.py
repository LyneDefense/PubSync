"""blogger_posts.note_key:稳定规范键(小红书 biz_id / 抖音 aweme_id),权威去重用。

在 0011 之上的增量迁移。加列前判存在,保证 create_all 与 stamp 升级两条路径都幂等。
存量回填(从 raw_json 取 biz_id)与重复合并由部署后的一次性脚本完成,不放迁移里。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_post_note_key"
down_revision = "0011_post_missed_crawl"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "note_key" not in _columns("blogger_posts"):
        op.add_column("blogger_posts", sa.Column("note_key", sa.String(length=64), nullable=False, server_default=""))
        op.create_index("ix_blogger_posts_note_key", "blogger_posts", ["note_key"])


def downgrade() -> None:
    if "note_key" in _columns("blogger_posts"):
        op.drop_index("ix_blogger_posts_note_key", table_name="blogger_posts")
        op.drop_column("blogger_posts", "note_key")
