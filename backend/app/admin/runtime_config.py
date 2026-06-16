"""运行时配置覆盖:把 ``system_config`` 表里的值叠加到 ``get_settings()`` 单例上。

设计要点:
- ``get_settings()`` 是 ``@lru_cache`` 单例,全进程共享同一对象引用。``apply_overrides`` 直接
  ``setattr`` 到这个对象上,因此**所有读 ``settings`` 的地方 0 改动**即可拿到覆盖后的值。
- ``apply_overrides`` 先把所有可覆盖字段**重置回 env 基线**,再叠加 DB 行 —— 天然幂等,
  也让「清除某项」自动回落到 .env 值。
- 生效时机:API 启动时、管理员保存/清除时(API 进程),以及 worker 每个任务开跑前
  (见 ``task_service.execute_task``)。多进程靠「每任务刷新 + 启动刷新」收敛,单后端容器足够。
- env 基线由一份**全新构造的 ``Settings()``** 提供(纯读 .env,不受单例已被改动影响)。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.config_registry import FIELDS_BY_KEY, GROUPS, OVERRIDABLE, ConfigField, coerce
from app.admin.secret_box import SecretBoxError, decrypt, encrypt
from app.config import Settings
from app.models import SystemConfig

logger = logging.getLogger(__name__)

_baseline_cache: dict[str, Any] | None = None


def _baseline() -> dict[str, Any]:
    """可覆盖字段的 env 基线值(只读一次 .env,与被改动的单例无关)。"""
    global _baseline_cache
    if _baseline_cache is None:
        env_only = Settings()
        _baseline_cache = {f.key: getattr(env_only, f.key) for f in OVERRIDABLE}
    return _baseline_cache


def _load_rows(db: Session) -> dict[str, SystemConfig]:
    return {row.key: row for row in db.scalars(select(SystemConfig))}


def apply_overrides(settings: Settings, db: Session) -> None:
    """把 DB 覆盖项叠加到 settings 单例;无覆盖的字段回落到 env 基线。"""
    base = _baseline()
    rows = _load_rows(db)
    for field in OVERRIDABLE:
        row = rows.get(field.key)
        if row is None:
            setattr(settings, field.key, base[field.key])
            continue
        try:
            raw = decrypt(settings, row.value) if field.is_secret else row.value
            setattr(settings, field.key, coerce(field, raw))
        except (ValueError, SecretBoxError):
            # 坏值/坏密文不应让整个配置加载崩掉:回落该字段到 env 基线并告警。
            logger.warning("配置覆盖项 %s 加载失败,已回落到 .env 值", field.key)
            setattr(settings, field.key, base[field.key])


def set_config(db: Session, settings: Settings, key: str, raw_value: str) -> None:
    """写入/更新一个覆盖项(密钥类先加密),并刷新当前进程单例。"""
    field = FIELDS_BY_KEY.get(key)
    if field is None:
        raise KeyError(key)
    stored = encrypt(settings, raw_value) if field.is_secret else raw_value
    db.merge(SystemConfig(key=key, value=stored, is_secret=field.is_secret))
    db.commit()
    apply_overrides(settings, db)


def clear_config(db: Session, settings: Settings, key: str) -> None:
    """删除一个覆盖项(回落到 .env),并刷新当前进程单例。"""
    if key not in FIELDS_BY_KEY:
        raise KeyError(key)
    row = db.get(SystemConfig, key)
    if row is not None:
        db.delete(row)
        db.commit()
    apply_overrides(settings, db)


def _field_view(field: ConfigField, settings: Settings, has_row: bool) -> dict[str, Any]:
    base = _baseline()
    effective = getattr(settings, field.key)
    source = "db" if has_row else "env"
    view: dict[str, Any] = {
        "key": field.key,
        "label": field.label,
        "type": field.type,
        "is_secret": field.is_secret,
        "source": source,
    }
    if field.is_secret:
        # 密钥绝不回传明文,只给「是否已配置」。
        view["configured"] = bool(str(effective).strip())
        if not has_row and not str(base[field.key]).strip():
            view["source"] = "unset"
    else:
        view["value"] = effective
    return view


def read_config_view(db: Session, settings: Settings) -> dict[str, Any]:
    """给前端的分组配置视图(密钥脱敏,绝不含明文)。"""
    rows = _load_rows(db)
    group_labels = dict(GROUPS)
    groups = []
    for group_key, label in GROUPS:
        fields = [
            _field_view(f, settings, f.key in rows)
            for f in OVERRIDABLE
            if f.group == group_key
        ]
        groups.append({"key": group_key, "label": group_labels[group_key], "fields": fields})
    return {"groups": groups}
