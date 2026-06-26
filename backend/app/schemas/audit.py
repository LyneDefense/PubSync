from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AccountAuditCreate(BaseModel):
    """对标诊断:我的账号(勾选内容)vs 对标账号(勾选内容)。"""

    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    my_blogger_id: int
    my_post_ids: list[int] = Field(default_factory=list)
    benchmark_blogger_id: int
    benchmark_post_ids: list[int] = Field(default_factory=list)


class SelfDiagnoseCreate(BaseModel):
    """诊断我的:只看我的账号(勾选内容)。"""

    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    my_blogger_id: int
    my_post_ids: list[int] = Field(default_factory=list)


class AppraiseCreate(BaseModel):
    """博主诊断:诊断一个号(对标库博主或我的账号)。诊断前自动确保 ≥N 条笔记。"""

    blogger_id: int
    kind: str = Field(default="benchmark", pattern="^(benchmark|self)$")
    intent: str = Field(default="", max_length=500)  # 对标意图(诊断别人时用,诊断自己忽略)
    industry: str | None = Field(default=None, max_length=50)  # 品类(触发合规红线,如「香港保险」)


class AccountAuditRunRead(BaseModel):
    id: int
    tenant_id: int
    platform: str
    kind: str
    my_blogger_id: int | None
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
