import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import Settings


EXTRA_USERS = {
    "eyangpet": "123456",
}

USER_TENANT_IDS = {
    "eyangpet": [2],
}


def create_token(settings: Settings, username: str | None = None) -> str:
    payload = {
        "sub": username or settings.admin_username,
        "exp": int(time.time()) + max(1, settings.session_hours) * 3600,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
    signature = sign(encoded_payload, settings)
    return f"{encoded_payload}.{signature}"


def verify_token(token: str, settings: Settings) -> bool:
    return token_username(token, settings) is not None


def token_username(token: str, settings: Settings) -> str | None:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = sign(encoded_payload, settings)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(pad_base64(encoded_payload)))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    username = str(payload.get("sub") or "")
    if not is_known_user(username, settings):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= time.time():
        return None
    return username


def verify_credentials(username: str, password: str, settings: Settings) -> bool:
    if hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(password, settings.admin_password):
        return True
    expected_password = EXTRA_USERS.get(username)
    return expected_password is not None and hmac.compare_digest(password, expected_password)


def is_known_user(username: str, settings: Settings) -> bool:
    return hmac.compare_digest(username, settings.admin_username) or username in EXTRA_USERS


def tenant_ids_for_user(username: str, settings: Settings) -> list[int]:
    if hmac.compare_digest(username, settings.admin_username):
        return [1]
    return USER_TENANT_IDS.get(username, [])


def sign(encoded_payload: str, settings: Settings) -> str:
    secret = settings.auth_secret or settings.admin_password
    digest = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def pad_base64(value: str) -> bytes:
    return f"{value}{'=' * (-len(value) % 4)}".encode()
