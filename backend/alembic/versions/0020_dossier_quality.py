"""博主画像提质:档案补充字段。

blogger_profiles:
- signature        —— 平台主页简介(与用户备注 description 分开;刷新资料时更新)
- liked_collected_count —— 账号级获赞与收藏总数(user_info,覆盖全部笔记;解析不到为 NULL)
- operating_habits_json —— 运营习惯事实模块(建档算:发布节奏/模态偏好/体裁/评论引导/博主回复)
- compliance_json  —— 合规体检(建档规则扫描结果)
加列前判存在,幂等。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_dossier_quality"
down_revision = "0019_blogger_dossier"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    profiles = _columns("blogger_profiles")
    if "signature" not in profiles:
        op.add_column("blogger_profiles", sa.Column("signature", sa.Text(), nullable=False, server_default=""))
    if "liked_collected_count" not in profiles:
        op.add_column("blogger_profiles", sa.Column("liked_collected_count", sa.Integer(), nullable=True))
    if "operating_habits_json" not in profiles:
        op.add_column("blogger_profiles", sa.Column("operating_habits_json", sa.Text(), nullable=False, server_default=""))
    if "compliance_json" not in profiles:
        op.add_column("blogger_profiles", sa.Column("compliance_json", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    profiles = _columns("blogger_profiles")
    for name in ("compliance_json", "operating_habits_json", "liked_collected_count", "signature"):
        if name in profiles:
            op.drop_column("blogger_profiles", name)
