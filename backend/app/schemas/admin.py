from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import TenantStatus


# —— 运行时配置 ——
class ConfigFieldView(BaseModel):
    key: str
    label: str
    type: str
    is_secret: bool
    source: str  # env | db | unset
    value: Any | None = None  # 仅非密钥字段回传
    configured: bool | None = None  # 仅密钥字段回传(是否已配置,绝不回明文)


class ConfigGroupView(BaseModel):
    key: str
    label: str
    fields: list[ConfigFieldView]


class ConfigView(BaseModel):
    groups: list[ConfigGroupView]


class ConfigUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(default="", max_length=4000)


# —— 任务队列 ——
class AdminTaskRead(BaseModel):
    id: str
    tenant_id: int
    task_type: str
    status: str
    message: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueueHealth(BaseModel):
    use_task_queue: bool
    queue_name: str | None = None
    queued: int | None = None
    failed: int | None = None
    note: str | None = None


# —— 工作空间 ——
class AdminTenantRead(BaseModel):
    id: int
    name: str
    slug: str
    status: TenantStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    password: str = Field(min_length=6, max_length=120)


# —— 费用台账 ——
class CostEventRead(BaseModel):
    id: int
    created_at: datetime
    tenant_id: int | None
    tenant_name: str | None = None
    task_id: str | None
    provider: str
    kind: str
    model: str | None
    quantity: int
    unit: str
    cost_usd: float
    meta_json: str | None


class CostByKey(BaseModel):
    key: str
    label: str
    cost_usd: float
    count: int


class CostSummary(BaseModel):
    days: int
    total_usd: float
    event_count: int
    by_provider: list[CostByKey]
    by_tenant: list[CostByKey]


class ModelPrices(BaseModel):
    text: dict[str, Any] = {}
    image: dict[str, Any] = {}
