"""TikHub 响应的通用解析原语(平台无关):取值兜底(unwrap/first_str/first_int)、计数与时间解析、递归查找、布尔判断。"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any


def unwrap_payload(data: Any) -> Any:
    current = data
    for _ in range(4):
        if isinstance(current, dict):
            for key in ("data", "result", "note", "notes", "items"):
                value = current.get(key)
                if value not in (None, "", []):
                    current = value
                    break
            else:
                return current
        else:
            return current
    return current


def first_str(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int)):
            return str(value).strip()
    return ""


def first_int(data: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            normalized = parse_count(value)
            if normalized is not None:
                return normalized
    return 0


def parse_count(value: str) -> int | None:
    text = value.replace(",", "").strip()
    if not text:
        return None
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10_000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def dig(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def recursive_find(value: Any, target_key: str) -> Any:
    if isinstance(value, dict):
        if target_key in value:
            return value[target_key]
        for child in value.values():
            result = recursive_find(child, target_key)
            if result not in (None, "", []):
                return result
    elif isinstance(value, list):
        for child in value:
            result = recursive_find(child, target_key)
            if result not in (None, "", []):
                return result
    return None


def parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, int):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def first_bool(data: dict[str, Any], keys: list[str]) -> bool:
    for key in keys:
        value = data.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n", ""}:
                return False
    return False


def first_bool_recursive(data: Any, keys: tuple[str, ...]) -> bool:
    if isinstance(data, dict):
        if first_bool(data, list(keys)):
            return True
        return any(first_bool_recursive(child, keys) for child in data.values())
    if isinstance(data, list):
        return any(first_bool_recursive(child, keys) for child in data)
    return False
