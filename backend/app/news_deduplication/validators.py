from typing import Any


def validate_duplicate_review(data: dict[str, Any]) -> tuple[bool, str]:
    is_duplicate = data.get("is_duplicate")
    if isinstance(is_duplicate, str):
        is_duplicate = is_duplicate.strip().lower() in {"true", "yes", "1", "是", "重复"}
    reason = str(data.get("reason") or "").strip()
    return bool(is_duplicate), reason or "大模型未给出明确原因"
