from app.config import Settings
from app.services import ai_service


def _settings(**kw):
    base = dict(llm_provider="claude", anthropic_api_key="sk-test", anthropic_text_model="claude-sonnet-4-6")
    base.update(kw)
    return Settings(**base)


def test_is_ai_enabled_claude():
    assert ai_service.is_ai_enabled(_settings()) is True
    assert ai_service.is_ai_enabled(_settings(anthropic_api_key="")) is False


def test_create_json_response_routes_to_anthropic(monkeypatch):
    captured = {}

    def fake_post(settings, path, payload, timeout):
        captured["path"] = path
        captured["model"] = payload["model"]
        return {"content": [{"type": "text", "text": '{"ok": true, "n": 3}'}], "usage": {"input_tokens": 5, "output_tokens": 7}}

    monkeypatch.setattr(ai_service, "anthropic_post", fake_post)
    out = ai_service.create_json_response(_settings(), "写点东西")
    assert out == {"ok": True, "n": 3}
    assert captured["path"] == "/v1/messages"
    assert captured["model"] == "claude-sonnet-4-6"


def test_anthropic_text_requires_key():
    import pytest

    with pytest.raises(ai_service.AIServiceError):
        ai_service.anthropic_text(_settings(anthropic_api_key=""), "x")
