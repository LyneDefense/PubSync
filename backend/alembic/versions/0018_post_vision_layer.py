"""博主笔记视觉层列:image_text + visual_digest + vision_status/error/image_count。

在 0017 之上的增量迁移。与 ASR 那组列对称,给图文笔记存"图内文字 + 视觉摘要"。
加列前判存在,幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0018_post_vision_layer"
down_revision = "0017_post_modality_signals"
branch_labels = None
depends_on = None

_TABLE = "blogger_posts"


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}


def upgrade() -> None:
    cols = _columns()
    if "image_text" not in cols:
        op.add_column(_TABLE, sa.Column("image_text", sa.Text(), nullable=False, server_default=""))
    if "visual_digest" not in cols:
        op.add_column(_TABLE, sa.Column("visual_digest", sa.Text(), nullable=False, server_default=""))
    if "vision_status" not in cols:
        op.add_column(_TABLE, sa.Column("vision_status", sa.String(length=30), nullable=False, server_default="not_required"))
    if "vision_error" not in cols:
        op.add_column(_TABLE, sa.Column("vision_error", sa.Text(), nullable=False, server_default=""))
    if "vision_image_count" not in cols:
        op.add_column(_TABLE, sa.Column("vision_image_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    cols = _columns()
    for name in ("vision_image_count", "vision_error", "vision_status", "visual_digest", "image_text"):
        if name in cols:
            op.drop_column(_TABLE, name)
