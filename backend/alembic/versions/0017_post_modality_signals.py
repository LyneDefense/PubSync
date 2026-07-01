"""博主笔记加模态判定信号列:duration_seconds + content_subtype_confidence。

在 0016 之上的增量迁移。加列前判存在,幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017_post_modality_signals"
down_revision = "0016_benchmark_discovery_session"
branch_labels = None
depends_on = None

_TABLE = "blogger_posts"


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}


def upgrade() -> None:
    cols = _columns()
    if "content_subtype_confidence" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("content_subtype_confidence", sa.String(length=20), nullable=False, server_default=""),
        )
    if "duration_seconds" not in cols:
        op.add_column(_TABLE, sa.Column("duration_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    cols = _columns()
    if "duration_seconds" in cols:
        op.drop_column(_TABLE, "duration_seconds")
    if "content_subtype_confidence" in cols:
        op.drop_column(_TABLE, "content_subtype_confidence")
