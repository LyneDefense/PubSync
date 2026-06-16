import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - 注册所有表到 Base.metadata
from app.admin import runtime_config
from app.admin.secret_box import SecretBoxError
from app.config import Settings
from app.database import Base
from app.models import SystemConfig


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _settings() -> Settings:
    return Settings(auth_secret="unit-secret")


def test_apply_overrides_sets_non_secret(db):
    settings = _settings()
    runtime_config.set_config(db, settings, "openai_text_model", "gpt-4o-mini")
    assert settings.openai_text_model == "gpt-4o-mini"
    # 全新 settings 经 apply_overrides 后得到同样的覆盖值(幂等)。
    fresh = _settings()
    runtime_config.apply_overrides(fresh, db)
    assert fresh.openai_text_model == "gpt-4o-mini"


def test_typed_coercion(db):
    settings = _settings()
    runtime_config.set_config(db, settings, "creation_min_quality_score", "92")
    assert settings.creation_min_quality_score == 92
    assert isinstance(settings.creation_min_quality_score, int)
    runtime_config.set_config(db, settings, "asr_enabled", "true")
    assert settings.asr_enabled is True


def test_secret_roundtrip_and_view_hides_plaintext(db):
    settings = _settings()
    runtime_config.set_config(db, settings, "openai_api_key", "sk-secret-123")
    # 进程内生效值是解密后的明文。
    assert settings.openai_api_key == "sk-secret-123"
    # 落库的是密文,不是明文。
    row = db.get(SystemConfig, "openai_api_key")
    assert row is not None and row.value != "sk-secret-123"
    # 视图对密钥只给「是否已配置」,绝不回明文。
    fields = [f for g in runtime_config.read_config_view(db, settings)["groups"] for f in g["fields"]]
    key_field = next(f for f in fields if f["key"] == "openai_api_key")
    assert key_field["is_secret"] is True
    assert key_field["configured"] is True
    assert key_field.get("value") is None


def test_clear_config_falls_back_to_env(db):
    settings = _settings()
    runtime_config.set_config(db, settings, "openai_text_model", "override-model")
    runtime_config.clear_config(db, settings, "openai_text_model")
    assert settings.openai_text_model == Settings().openai_text_model


def test_unknown_or_infra_key_rejected(db):
    settings = _settings()
    with pytest.raises(KeyError):
        runtime_config.set_config(db, settings, "database_url", "evil")
    with pytest.raises(KeyError):
        runtime_config.set_config(db, settings, "not_a_field", "x")


def test_secret_requires_encryption_key(db):
    settings = Settings(auth_secret="", config_encryption_key="")
    with pytest.raises(SecretBoxError):
        runtime_config.set_config(db, settings, "openai_api_key", "sk-x")
