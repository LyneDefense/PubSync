import base64
import hashlib
import hmac
import json
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User


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
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= time.time():
        return None
    return username


def verify_credentials(username: str, password: str, settings: Settings, db: Session | None = None) -> bool:
    if db is not None:
        user = get_user_by_username(db, username)
        return bool(user and user.status == "active" and verify_password(password, user.password_hash, settings))
    # 无数据库时（极少见）只认配置里的管理员账号，不再有任何硬编码账号。
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(
        password, settings.admin_password
    )


def is_known_user(username: str, settings: Settings, db: Session | None = None) -> bool:
    if db is not None:
        user = get_user_by_username(db, username)
        return bool(user and user.status == "active")
    return hmac.compare_digest(username, settings.admin_username)


def tenant_ids_for_user(username: str, settings: Settings, db: Session | None = None) -> list[int]:
    if db is not None:
        user = get_user_by_username(db, username)
        if user and user.status == "active":
            if user.is_admin:
                return [1]
            return [user.tenant_id] if user.tenant_id else []
        return []
    if is_admin_user(username, settings, db):
        return [1]
    return []


def is_admin_user(username: str, settings: Settings, db: Session | None = None) -> bool:
    if db is not None:
        user = get_user_by_username(db, username)
        return bool(user and user.status == "active" and user.is_admin)
    return hmac.compare_digest(username, settings.admin_username)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def hash_password(password: str, settings: Settings) -> str:
    salt = settings.auth_secret or settings.admin_password
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(digest).decode().rstrip('=')}"


def verify_password(password: str, password_hash: str, settings: Settings) -> bool:
    # 只接受 PBKDF2 哈希；历史明文或未知格式一律视为无效（不再做明文兜底）。
    if not password_hash.startswith("pbkdf2_sha256$"):
        return False
    return hmac.compare_digest(password_hash, hash_password(password, settings))


def sign(encoded_payload: str, settings: Settings) -> str:
    secret = settings.auth_secret or settings.admin_password
    digest = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def pad_base64(value: str) -> bytes:
    return f"{value}{'=' * (-len(value) % 4)}".encode()
