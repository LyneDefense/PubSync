from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class XhsPublishPackageCreate(BaseModel):
    skill_id: int
    content_type: str = Field(pattern="^(text_note|image_note|spoken_script|video_script)$")
    topic: str = Field(min_length=1, max_length=300)
    target_audience: str = Field(default="", max_length=300)
    content_goal: str = Field(default="", max_length=120)
    keywords: str = Field(default="", max_length=500)
    image_count_mode: str = Field(default="auto", pattern="^(auto|manual)$")
    requested_image_count: int | None = Field(default=None, ge=1, le=9)


class XhsPublishPackageDraftRead(BaseModel):
    tenant_id: int
    blogger_id: int
    skill_id: int
    content_type: str
    topic: str
    target_audience: str
    content_goal: str
    keywords: str
    image_count_mode: str
    requested_image_count: int | None
    title: str
    body_text: str
    hashtags_json: str
    cover_text: str
    image_plan_json: str
    image_urls_json: str
    script_json: str
    status: str
    error_message: str | None


class XhsPublishPackageSave(BaseModel):
    skill_id: int
    content_type: str = Field(pattern="^(text_note|image_note|spoken_script|video_script)$")
    topic: str = Field(min_length=1, max_length=300)
    target_audience: str = Field(default="", max_length=300)
    content_goal: str = Field(default="", max_length=120)
    keywords: str = Field(default="", max_length=500)
    image_count_mode: str = Field(default="auto", pattern="^(auto|manual)$")
    requested_image_count: int | None = Field(default=None, ge=1, le=9)
    title: str = Field(default="", max_length=300)
    body_text: str = ""
    hashtags_json: str = "[]"
    cover_text: str = Field(default="", max_length=300)
    image_plan_json: str = "[]"
    image_urls_json: str = "[]"
    script_json: str = "{}"
    error_message: str | None = None


class XhsTopicIdeaRequest(BaseModel):
    skill_id: int
    seed_topic: str = Field(default="", max_length=300)
    target_audience: str = Field(default="", max_length=300)
    content_goal: str = Field(default="", max_length=120)
    keywords: str = Field(default="", max_length=500)


class XhsTopicIdeaRead(BaseModel):
    title: str
    angle: str
    target_audience: str
    content_goal: str
    keywords: list[str]
    reason: str


class XhsTopicIdeaResponse(BaseModel):
    ideas: list[XhsTopicIdeaRead]


class XhsPublishPackageRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    skill_id: int
    content_type: str
    topic: str
    target_audience: str
    content_goal: str
    keywords: str
    image_count_mode: str
    requested_image_count: int | None
    title: str
    body_text: str
    hashtags_json: str
    cover_text: str
    image_plan_json: str
    image_urls_json: str
    script_json: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
