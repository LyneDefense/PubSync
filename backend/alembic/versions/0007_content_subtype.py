"""内容模态细分:blogger_posts.content_subtype + blogger_skills.scope_json。

在 0001 baseline 之上的增量迁移(给既有表加列)。0001 用 ``Base.metadata.create_all`` 基于当前 ORM
建表,全新库已带新列;线上既有库缺列,只跑本迁移补列。做列存在性判断,保证两条路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_content_subtype"
down_revision = "0006_blogger_tags"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "content_subtype" not in _columns("blogger_posts"):
        op.add_column(
            "blogger_posts",
            sa.Column("content_subtype", sa.String(length=30), nullable=False, server_default="unknown"),
        )
        op.create_index("ix_blogger_posts_content_subtype", "blogger_posts", ["content_subtype"])

    if "scope_json" not in _columns("blogger_skills"):
        op.add_column(
            "blogger_skills",
            sa.Column("scope_json", sa.Text(), nullable=False, server_default='["__all__"]'),
        )


def downgrade() -> None:
    if "scope_json" in _columns("blogger_skills"):
        op.drop_column("blogger_skills", "scope_json")
    if "content_subtype" in _columns("blogger_posts"):
        op.drop_index("ix_blogger_posts_content_subtype", table_name="blogger_posts")
        op.drop_column("blogger_posts", "content_subtype")
