from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AccountAuditCreate(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    benchmark_skill_id: int
    my_content_text: str = Field(min_length=1, max_length=20000)
    # 预留:本轮前端只走手动粘贴,后续可改为复用已采集的「我自己」博主。
    benchmark_blogger_id: int | None = None


class AccountAuditRunRead(BaseModel):
    id: int
    tenant_id: int
    platform: str
    benchmark_blogger_id: int | None
    benchmark_skill_id: int | None
    task_id: str | None
    status: str
    input_snapshot: str
    report_json: str
    score: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountAuditReport(BaseModel):
    """report_json 的结构(供前端/文档参考,后端不强校验)。"""

    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    conclusion: str = ""
    score: int | None = None
