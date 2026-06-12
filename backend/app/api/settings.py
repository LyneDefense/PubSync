from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models import AppSetting
from app.schemas import SettingRead, SettingUpdate

router = APIRouter()


@router.get("/settings", response_model=list[SettingRead])
def list_settings_endpoint(_: str = Depends(require_admin), db: Session = Depends(get_db)) -> list[AppSetting]:
    return list(db.scalars(select(AppSetting).order_by(AppSetting.key.asc())))


@router.put("/settings/{key}", response_model=SettingRead)
def upsert_setting_endpoint(
    key: str,
    payload: SettingUpdate,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AppSetting:
    setting = db.merge(AppSetting(key=key, value=payload.value))
    db.commit()
    db.refresh(setting)
    return setting
