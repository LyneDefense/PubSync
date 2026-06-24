from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SkillOptimizeRequest(BaseModel):
    epochs: int = Field(default=2, ge=1, le=5)
    # 要优化的 Skill 版本;不传则用该博主当前 active Skill。
    skill_id: int | None = None


class SkillOptimizeConfirm(BaseModel):
    adopt: bool


class SkillTrainingRunRead(BaseModel):
    id: int
    blogger_id: int
    base_skill_id: int | None = None
    result_skill_id: int | None = None
    status: str
    modality: str
    before_score: float
    after_score: float
    before_gap: float
    after_gap: float
    delta: float
    verdict: str
    recommend_adopt: bool
    optimized_skill_markdown: str = ""
    report: dict = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
