"""博主内容标签:blogger_profiles.tags_json。

在 0001 baseline 之上的增量迁移(给既有表加列)。0001 用 ``Base.metadata.create_all`` 基于当前 ORM
建表,全新库已带新列;线上既有库缺列,只跑本迁移补列。做列存在性判断,保证两条路径都幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_blogger_tags"
down_revision = "0005_account_module"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "tags_json" not in _columns("blogger_profiles"):
        op.add_column(
            "blogger_profiles",
            sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    if "tags_json" in _columns("blogger_profiles"):
        op.drop_column("blogger_profiles", "tags_json")
