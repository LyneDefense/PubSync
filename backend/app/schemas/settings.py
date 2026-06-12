from pydantic import BaseModel, ConfigDict


class SettingRead(BaseModel):
    key: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class SettingUpdate(BaseModel):
    value: str
