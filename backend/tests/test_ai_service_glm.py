"""GLM(智谱)文本供应商接线单测。"""

from types import SimpleNamespace

from app.services import ai_service


def _settings(**kw):
    base = dict(
        llm_provider="glm", glm_api_key="k", glm_base_url="https://x", glm_text_model="glm-4.6",
        openai_api_key="", minimax_api_key="", anthropic_api_key="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_is_ai_enabled_glm():
    assert ai_service.is_ai_enabled(_settings()) is True
    assert ai_service.is_ai_enabled(_settings(glm_api_key="")) is False


def test_glm_text_parses_openai_style(monkeypatch):
    monkeypatch.setattr(ai_service, "record_text_usage", lambda *a, **k: None)
    monkeypatch.setattr(ai_service, "glm_post", lambda *a, **k: {"choices": [{"message": {"content": '{"ok":1}'}}]})
    assert ai_service.glm_text(_settings(), "prompt") == '{"ok":1}'


def test_create_json_response_routes_to_glm(monkeypatch):
    monkeypatch.setattr(ai_service, "record_text_usage", lambda *a, **k: None)
    monkeypatch.setattr(ai_service, "glm_post", lambda *a, **k: {"choices": [{"message": {"content": '{"a": 2}'}}]})
    assert ai_service.create_json_response(_settings(), "prompt") == {"a": 2}


def test_glm_text_requires_key():
    import pytest
    with pytest.raises(ai_service.AIServiceError):
        ai_service.glm_text(_settings(glm_api_key=""), "p")
