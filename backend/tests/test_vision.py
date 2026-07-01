"""视觉层单测:响应解析、选图、provider 路由、图片理解步骤、post_content 装配。

不触真实网络:glm_vision_chat 打桩。
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.blogger_distillation.vision as vision_mod
import app.models  # noqa: F401 - 注册所有表
from app.blogger_distillation.post_content import assemble_learnable_text, visual_context, visual_digest_dict
from app.blogger_distillation.service.vision_step import handle_note_vision
from app.blogger_distillation.vision import (
    DisabledVisionProvider,
    GlmVisionProvider,
    VisionError,
    VisionResult,
    build_vision_provider,
    parse_vision_response,
    select_note_images,
)
from app.config import Settings
from app.database import Base
from app.models import BloggerProfile, Tenant


def _settings(**overrides) -> Settings:
    base = {
        "vision_enabled": True,
        "vision_provider": "glm",
        "vision_model": "glm-4.6v",
        "vision_scope": "cover_body",
        "vision_max_images_per_note": 4,
        "glm_api_key": "test-key",
    }
    base.update(overrides)
    return Settings(**base)


class _FakePost:
    def __init__(self, **kw):
        self.title = kw.get("title", "")
        self.body_text = kw.get("body_text", "")
        self.transcript_text = kw.get("transcript_text", "")
        self.image_text = kw.get("image_text", "")
        self.visual_digest = kw.get("visual_digest", "")


class _FakeCandidate:
    def __init__(self, external_id="note-1"):
        self.external_id = external_id


class _FakeProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def analyze_images(self, image_urls, *, source_id="", on_progress=None):
        self.calls.append(list(image_urls))
        if on_progress:
            on_progress("正在识别并理解图片…")
        return self.result


# —— 响应解析 ——

def test_parse_vision_response_json():
    text, digest = parse_vision_response('{"image_text":"你好世界","visual_digest":{"cover_hook":"钩子","layout":"卡片"}}')
    assert text == "你好世界"
    assert digest == {"cover_hook": "钩子", "layout": "卡片"}


def test_parse_vision_response_code_fence():
    raw = '```json\n{"image_text":"甲乙","visual_digest":{}}\n```'
    text, digest = parse_vision_response(raw)
    assert text == "甲乙"
    assert digest == {}


def test_parse_vision_response_non_json_falls_back_to_text():
    text, digest = parse_vision_response("这就是图里的一段文字，没有 JSON")
    assert "图里的一段文字" in text
    assert digest == {}


# —— 选图 ——

def test_select_images_cover_only():
    got = select_note_images("http://c/cover.jpg", ["http://c/cover.jpg", "http://c/b1.jpg"], scope="cover", max_body_images=4)
    assert got == ["http://c/cover.jpg"]


def test_select_images_cover_body_dedup_and_video_filtered():
    media = ["http://c/cover.jpg", "http://c/b1.jpg", "http://v/x.mp4", "http://c/b2.jpg"]
    got = select_note_images("http://c/cover.jpg", media, scope="cover_body", max_body_images=4)
    assert got == ["http://c/cover.jpg", "http://c/b1.jpg", "http://c/b2.jpg"]  # 去重封面 + 过滤视频


def test_select_images_caps_at_five():
    media = [f"http://c/{i}.jpg" for i in range(10)]
    got = select_note_images("http://c/cover.jpg", media, scope="cover_body", max_body_images=8)
    assert len(got) == 5


# —— provider 路由 ——

def test_build_provider_returns_glm():
    assert isinstance(build_vision_provider(_settings()), GlmVisionProvider)


def test_build_provider_disabled():
    assert isinstance(build_vision_provider(_settings(vision_enabled=False)), DisabledVisionProvider)


def test_build_provider_missing_key_raises():
    with pytest.raises(VisionError, match="GLM API Key"):
        build_vision_provider(_settings(glm_api_key=""))


def test_analyze_images_parses_result(monkeypatch):
    monkeypatch.setattr(
        vision_mod,
        "glm_vision_chat",
        lambda settings, *, image_parts, instruction, model=None: '{"image_text":"卡片要点","visual_digest":{"cover_hook":"每天拆解一个博主"}}',
    )
    provider = GlmVisionProvider(_settings())
    result = provider.analyze_images(["http://c/cover.jpg", "http://c/b1.jpg"], source_id="n1")
    assert result.image_text == "卡片要点"
    assert result.visual_digest == {"cover_hook": "每天拆解一个博主"}
    assert result.image_count == 2
    assert result.provider == "glm_vision"


def test_analyze_images_no_urls_raises():
    with pytest.raises(VisionError, match="没有可解析的图片"):
        GlmVisionProvider(_settings()).analyze_images(["not-a-url"])


# —— post_content 装配 ——

def test_assemble_learnable_text_includes_image_text():
    post = _FakePost(title="标题", body_text="正文", image_text="图内卡片文字")
    text = assemble_learnable_text(post)
    assert "标题" in text and "正文" in text and "图内卡片文字" in text
    assert "[图内文字]" in text


def test_visual_context_from_digest():
    post = _FakePost(visual_digest='{"cover_hook":"钩子","layout":"清单","info_points":["点1","点2"]}')
    ctx = visual_context(post)
    assert "封面文案：钩子" in ctx
    assert "版式：清单" in ctx
    assert "点1" in ctx


def test_visual_digest_dict_bad_json():
    assert visual_digest_dict(_FakePost(visual_digest="not json")) == {}


# —— 图片理解步骤 ——

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add(Tenant(id=1, name="T", slug="t"))
        session.add(BloggerProfile(id=1, tenant_id=1, platform="xhs", account_type="benchmark", display_name="大V", homepage_url="h"))
        session.commit()
        yield session
    finally:
        session.close()


def test_handle_note_vision_success(db):
    blogger = db.get(BloggerProfile, 1)
    normalized = {"cover_url": "http://c/cover.jpg", "media_urls_json": '["http://c/cover.jpg","http://c/b1.jpg"]'}
    provider = _FakeProvider(VisionResult(image_text="图内文字", visual_digest={"cover_hook": "钩子"}, image_count=2, provider="glm_vision"))
    handle_note_vision(db, 1, "task-1", _FakeCandidate(), normalized, provider, blogger, _settings())
    assert normalized["vision_status"] == "succeeded"
    assert normalized["image_text"] == "图内文字"
    assert '"cover_hook"' in normalized["visual_digest"]
    assert normalized["vision_image_count"] == 2
    assert provider.calls == [["http://c/cover.jpg", "http://c/b1.jpg"]]


def test_handle_note_vision_disabled_provider_skips(db):
    blogger = db.get(BloggerProfile, 1)
    normalized = {"cover_url": "http://c/cover.jpg", "media_urls_json": "[]"}
    handle_note_vision(db, 1, "task-1", _FakeCandidate(), normalized, None, blogger, _settings())
    assert normalized["vision_status"] == "skipped"


def test_handle_note_vision_no_images_skips(db):
    blogger = db.get(BloggerProfile, 1)
    normalized = {"cover_url": "", "media_urls_json": "[]"}
    provider = _FakeProvider(VisionResult())
    handle_note_vision(db, 1, "task-1", _FakeCandidate(), normalized, provider, blogger, _settings())
    assert normalized["vision_status"] == "skipped"
    assert normalized["vision_error"] == "无可解析图片"
