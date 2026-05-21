import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import Settings


def create_token(settings: Settings) -> str:
    payload = {
        "sub": settings.admin_username,
        "exp": int(time.time()) + max(1, settings.session_hours) * 3600,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
    signature = sign(encoded_payload, settings)
    return f"{encoded_payload}.{signature}"


def verify_token(token: str, settings: Settings) -> bool:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return False
    expected = sign(encoded_payload, settings)
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        payload = json.loads(base64.urlsafe_b64decode(pad_base64(encoded_payload)))
    except (ValueError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("sub") != settings.admin_username:
        return False
    exp = payload.get("exp")
    return isinstance(exp, int) and exp > time.time()


def verify_credentials(username: str, password: str, settings: Settings) -> bool:
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(password, settings.admin_password)


def sign(encoded_payload: str, settings: Settings) -> str:
    secret = settings.auth_secret or settings.admin_password
    digest = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def pad_base64(value: str) -> bytes:
    return f"{value}{'=' * (-len(value) % 4)}".encode()
