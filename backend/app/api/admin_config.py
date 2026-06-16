"""后台运行时配置 API:查看 / 修改 / 清除模型/ASR/采集等运营配置。

均需管理员;密钥类配置加密落库、绝不回传明文。基础设施字段不在白名单内,无法在此修改。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.admin.runtime_config import clear_config, read_config_view, set_config
from app.admin.secret_box import SecretBoxError
from app.api.deps import require_admin, settings
from app.database import get_db
from app.schemas import ConfigUpdate, ConfigView

router = APIRouter()


@router.get("/admin/config", response_model=ConfigView)
def get_config_endpoint(_: str = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return read_config_view(db, settings)


@router.put("/admin/config", response_model=ConfigView)
def update_config_endpoint(
    payload: ConfigUpdate,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        set_config(db, settings, payload.key, payload.value)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="不支持修改该配置项") from exc
    except SecretBoxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return read_config_view(db, settings)


@router.delete("/admin/config/{key}", response_model=ConfigView)
def clear_config_endpoint(
    key: str,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        clear_config(db, settings, key)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="不支持修改该配置项") from exc
    return read_config_view(db, settings)
