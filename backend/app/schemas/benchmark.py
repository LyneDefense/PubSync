from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.blogger import BloggerSearchResultRead


class BenchmarkIntent(BaseModel):
    """用户意图:推荐/评分的参照系基础(永远必填,即使绑了"我的账号")。"""

    niche: str = Field(min_length=1, max_length=160)
    audience: str = Field(default="", max_length=160)
    goal: str = Field(default="", max_length=40)  # 涨粉立人设 / 私域获客 / 带货(前端给标签)
    content_form: str = Field(default="any", pattern="^(image_text|video|any)$")


class CandidateScore(BaseModel):
    """一个候选博主 + 评估结果。随推荐/评分结果返回,也是 run.candidates_json 的元素。"""

    platform: str
    external_id: str
    display_name: str
    homepage_url: str = ""
    avatar_url: str = ""
    description: str = ""
    follower_count: int = 0
    # 四项指标(0-100);transferability 仅当绑了"我的账号"时给。
    popularity: float = 0
    relevance: float = 0
    learnability: float = 0
    transferability: float | None = None
    overall: float = 0
    active: bool = True  # 活跃度 gate:近期无更新则 False 并降权
    # 判断依据:{"relevance": str, "learnability": str, "summary": str}
    reasons: dict = Field(default_factory=dict)
    # 已在库(已采过)则给 id,前端可直接"采用"且复用已有笔记。
    existing_blogger_id: int | None = None


class RecommendRequest(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    intent: BenchmarkIntent
    my_account_id: int | None = None  # 可选;多账号时前端强制选一个


class EvaluateRequest(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    intent: BenchmarkIntent
    my_account_id: int | None = None
    # 二选一:已有候选(来自搜索结果)或粘贴主页链接。
    candidate: BloggerSearchResultRead | None = None
    homepage_url: str | None = Field(default=None, max_length=1000)


class EvaluateResult(BaseModel):
    candidate: CandidateScore


# —— 泛搜索(发现会话)请求体 ——
class DiscoveryStartRequest(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    domains: list[str] = Field(min_length=1)        # 必填,可多个领域
    my_account_id: int | None = None                 # 可选,初始种子账号


class DiscoveryDirection(BaseModel):
    label: str
    weight: float = 50.0
    reason: str = ""
    selected: bool = True


class DiscoveryDirectionsRequest(BaseModel):
    directions: list[DiscoveryDirection] = Field(default_factory=list)


class DiscoveryReviewRequest(BaseModel):
    adopt_ids: list[str] = Field(default_factory=list)
    seed_ids: list[str] = Field(default_factory=list)
    choice: str = Field(default="more", pattern="^(more|seed_more|change_directions|finish)$")
    text: str = Field(default="", max_length=300)


class BenchmarkRecommendationRunRead(BaseModel):
    id: int
    platform: str
    kind: str
    status: str
    my_account_id: int | None = None
    intent: dict = Field(default_factory=dict)
    candidates: list[CandidateScore] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
