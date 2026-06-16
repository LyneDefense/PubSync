"""密钥类配置的对称加解密。

后台允许编辑 API key 等敏感配置,但**明文绝不落库**:存库前用 Fernet 加密,读出后解密。
加密钥优先取 ``settings.config_encryption_key``,留空则由 ``settings.auth_secret`` 派生
(sha256 → urlsafe-base64,正好 32 字节符合 Fernet 要求)。两者都为空时(本地默认)
``encrypt`` 抛错,从而让上层拒绝保存密钥(fail-safe),避免用空钥/弱钥加密。
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


class SecretBoxError(RuntimeError):
    """加密钥缺失或密文损坏时抛出。"""


def _fernet(settings: Settings) -> Fernet:
    raw = (settings.config_encryption_key or "").strip() or (settings.auth_secret or "").strip()
    if not raw:
        raise SecretBoxError("未配置 config_encryption_key / auth_secret，无法加密密钥类配置")
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(settings: Settings, plaintext: str) -> str:
    return _fernet(settings).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(settings: Settings, token: str) -> str:
    try:
        return _fernet(settings).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:  # 密文损坏 / 加密钥已变更
        raise SecretBoxError("密钥类配置解密失败（加密钥可能已变更）") from exc
