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
    intent: str = Field(default="", max_length=500)  # 意图:对标=想学什么;自诊=目标/痛点/阶段
    industry: str | None = Field(default=None, max_length=50)  # 品类(触发合规红线,如「香港保险」)


class AppraisalIntentSuggestRequest(BaseModel):
    """意图引导:看选中账号在做什么,帮用户把意图问清楚。
    kind=benchmark → 对标别人(想学什么);kind=self → 诊断自己(目标/痛点/阶段)。"""

    blogger_id: int
    intent: str = Field(default="", max_length=500)
    kind: str = Field(default="benchmark", pattern="^(benchmark|self)$")


class AppraisalIntentQuestion(BaseModel):
    q: str
    options: list[str] = Field(default_factory=list)


class AppraisalIntentSuggestResult(BaseModel):
    clear: bool  # 用户填的意图是否已够具体(够则前端直接放行诊断,不展示问题)
    questions: list[AppraisalIntentQuestion] = Field(default_factory=list)


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
