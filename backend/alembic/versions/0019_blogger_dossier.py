"""博主档案(笔记池两级 + 档案状态列)。

- blogger_posts:detail_level(list/full,存量默认 full)、view_count、xsec_token。
- blogger_profiles:pool_synced_at / pool_reached_end / attribution_json / build_task_id。
加列前判存在,幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0019_blogger_dossier"
down_revision = "0018_post_vision_layer"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    posts = _columns("blogger_posts")
    if "view_count" not in posts:
        op.add_column("blogger_posts", sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))
    if "detail_level" not in posts:
        op.add_column("blogger_posts", sa.Column("detail_level", sa.String(length=10), nullable=False, server_default="full"))
        op.create_index("ix_blogger_posts_detail_level", "blogger_posts", ["detail_level"])
    if "xsec_token" not in posts:
        op.add_column("blogger_posts", sa.Column("xsec_token", sa.String(length=300), nullable=False, server_default=""))

    profiles = _columns("blogger_profiles")
    if "pool_synced_at" not in profiles:
        op.add_column("blogger_profiles", sa.Column("pool_synced_at", sa.DateTime(timezone=True), nullable=True))
    if "pool_reached_end" not in profiles:
        op.add_column("blogger_profiles", sa.Column("pool_reached_end", sa.Boolean(), nullable=False, server_default="false"))
    if "attribution_json" not in profiles:
        op.add_column("blogger_profiles", sa.Column("attribution_json", sa.Text(), nullable=False, server_default=""))
    if "build_task_id" not in profiles:
        op.add_column("blogger_profiles", sa.Column("build_task_id", sa.String(length=36), nullable=False, server_default=""))


def downgrade() -> None:
    profiles = _columns("blogger_profiles")
    for name in ("build_task_id", "attribution_json", "pool_reached_end", "pool_synced_at"):
        if name in profiles:
            op.drop_column("blogger_profiles", name)
    posts = _columns("blogger_posts")
    if "detail_level" in posts:
        op.drop_index("ix_blogger_posts_detail_level", table_name="blogger_posts")
        op.drop_column("blogger_posts", "detail_level")
    for name in ("xsec_token", "view_count"):
        if name in posts:
            op.drop_column("blogger_posts", name)
