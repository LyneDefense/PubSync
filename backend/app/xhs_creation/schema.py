"""创作域 LLM 输出的 typed return(Pydantic 单一源)。见 docs/prompt治理_方案设计.md 支柱一。

一个模型同时驱动三件事,消灭 schema drift:
  (a) 给模型的 schema —— render_schema(TopicIdeas) 生成,注入 prompt;
  (b) 解析+校验     —— TopicIdeas.model_validate(raw),取代手写 normalize;
  (c) 调用方静态类型 —— idea.title 是 str,改字段名 mypy 报错。
field_validator(mode="before") 承接原 normalize 的宽松清洗(None→""、非 str→str、keywords 归一)。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.xhs_creation.normalize import normalize_string_list


class TopicIdea(BaseModel):
    model_config = ConfigDict(extra="ignore")  # 模型多吐的字段忽略,兼容

    title: str = Field("", description="选题标题,不超过 32 个汉字")
    angle: str = Field("", description="具体切入角度")
    target_audience: str = Field("", description="适合的读者")
    content_goal: str = Field("", description="知识分享/避坑科普/种草转化/观点表达/经验复盘")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    reason: str = Field("", description="为什么这个选题值得做(点出它回应了读者哪个真实需求)")

    @field_validator("title", "angle", "target_audience", "content_goal", "reason", mode="before")
    @classmethod
    def _clean_str(cls, v: object) -> str:
        return str(v or "").strip()

    @field_validator("keywords", mode="before")
    @classmethod
    def _clean_keywords(cls, v: object) -> list[str]:
        return normalize_string_list(v)


class TopicIdeas(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ideas: list[TopicIdea] = Field(default_factory=list)

    @field_validator("ideas", mode="before")
    @classmethod
    def _only_dicts(cls, v: object) -> list:
        # AI 偶尔在 ideas 里塞非对象项;跳过(等价原 `if isinstance(item, dict)` 过滤)。
        return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []
