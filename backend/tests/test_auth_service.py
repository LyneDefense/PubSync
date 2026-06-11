from app.config import Settings
from app.services import auth_service


def _settings(**overrides) -> Settings:
    base = {"auth_secret": "unit-test-secret", "session_hours": 24}
    base.update(overrides)
    return Settings(**base)


def test_token_roundtrip_recovers_username():
    settings = _settings()
    token = auth_service.create_token(settings, "alice")
    assert auth_service.token_username(token, settings) == "alice"
    assert auth_service.verify_token(token, settings) is True


def test_tampered_signature_is_rejected():
    settings = _settings()
    token = auth_service.create_token(settings, "alice")
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    assert auth_service.token_username(tampered, settings) is None


def test_token_signed_with_other_secret_is_rejected():
    token = auth_service.create_token(_settings(auth_secret="secret-a"), "bob")
    assert auth_service.token_username(token, _settings(auth_secret="secret-b")) is None


def test_garbage_token_is_rejected():
    settings = _settings()
    assert auth_service.token_username("not-a-token", settings) is None
    assert auth_service.token_username("", settings) is None


def test_password_hash_roundtrip():
    settings = _settings()
    hashed = auth_service.hash_password("pw-123", settings)
    assert hashed.startswith("pbkdf2_sha256$")
    assert auth_service.verify_password("pw-123", hashed, settings) is True
    assert auth_service.verify_password("wrong", hashed, settings) is False
