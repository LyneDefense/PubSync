from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import utc_now


class SystemConfig(Base):
    """全局运行时配置覆盖项(非租户级)。

    用于让管理员在后台编辑模型/ASR/抓取等运营配置,运行时覆盖 ``.env`` 加载的
    ``Settings`` 单例,无需改 .env 或重新部署。``value`` 为字符串;``is_secret`` 为真时
    ``value`` 是 Fernet 加密后的密文(明文绝不落库、也绝不回传前端)。基础设施字段
    (database_url/redis_url/auth_secret 等)不在可覆盖白名单内,仍只走 .env。
    """

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
