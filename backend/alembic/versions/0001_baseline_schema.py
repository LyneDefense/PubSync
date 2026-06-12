"""baseline schema — 基于 ORM 模型建表并灌入默认数据

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-12

这是数据库的初始迁移，也是 schema 的唯一权威来源：

* upgrade：用 ``Base.metadata.create_all`` 基于 21 个 ORM 模型创建全部表、索引、
  枚举类型，再调用 ``seed_default_data`` 灌入两个默认工作空间的种子数据。
* downgrade：``Base.metadata.drop_all`` 删除全部表。

后续 schema 变更请改 ``app/models`` 后用
``alembic revision --autogenerate -m "..."`` 生成新的迁移。
"""

from __future__ import annotations

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    import app.models  # noqa: F401 —— 导入以把所有表注册到 Base.metadata
    from app.database import Base
    from app.db.bootstrap import seed_default_data

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    seed_default_data(bind)


def downgrade() -> None:
    import app.models  # noqa: F401
    from app.database import Base

    Base.metadata.drop_all(bind=op.get_bind())
