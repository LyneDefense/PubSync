"""博主笔记视频档案列:video_profile + video_tags。

在 0024 之上的增量迁移。video_profile = 分层结构化 JSON(L0/L1/L2),
取代 content_subtype 作为「门」;video_tags = 从 profile 派生的展示/筛选标签。
加列前判存在,幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0025_video_profile"
down_revision = "0024_drop_benchmark_discovery"
branch_labels = None
depends_on = None

_TABLE = "blogger_posts"


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}


def upgrade() -> None:
    cols = _columns()
    if "video_profile" not in cols:
        op.add_column(_TABLE, sa.Column("video_profile", sa.Text(), nullable=False, server_default=""))
    if "video_tags" not in cols:
        op.add_column(_TABLE, sa.Column("video_tags", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    cols = _columns()
    for name in ("video_tags", "video_profile"):
        if name in cols:
            op.drop_column(_TABLE, name)
