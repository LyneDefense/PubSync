from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import TaskStatus


class OperationTaskRead(BaseModel):
    id: str
    tenant_id: int
    task_type: str
    status: TaskStatus
    message: str
    article_id: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationTaskEventRead(BaseModel):
    id: int
    tenant_id: int
    task_id: str
    step_name: str
    status: str
    message: str
    payload_json: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
