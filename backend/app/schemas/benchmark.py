from pydantic import BaseModel, Field


# —— 泛搜索/找相似(发现会话)请求体 ——
class DiscoveryStartRequest(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    domains: list[str] = Field(min_length=1)        # 泛搜索:必填,可多个领域


class DiscoverySimilarRequest(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    blogger_ids: list[int] = Field(min_length=1)    # 找相似:对标库里挑 1+ 个当参照


class DiscoveryAngleRequest(BaseModel):
    # 角度收窄:toggle 选/取消、reject 排除、propose 再推一批、begin 开始搜。
    op: str = Field(pattern="^(toggle|reject|propose|begin)$")
    labels: list[str] = Field(default_factory=list)


class DiscoveryOpRequest(BaseModel):
    # 候选阶段:采用 / 不要 / 移除已选 / 清空候选。
    op: str = Field(pattern="^(adopt|dismiss|remove_selected|clear_candidates)$")
    ids: list[str] = Field(default_factory=list)
