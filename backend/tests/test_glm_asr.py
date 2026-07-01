"""GLM-ASR-2512 provider 单测:分段拼接、请求构造、错误处理、provider 路由。

不触真实网络 / ffmpeg:module 级 helper(下载/探测/切分)与 httpx.post 全部打桩。
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

import app.blogger_distillation.asr as asr_mod
from app.blogger_distillation.asr import (
    ASRError,
    GlmAsrASRProvider,
    TencentRecTaskASRProvider,
    build_asr_provider,
)
from app.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "asr_enabled": True,
        "asr_provider": "glm_asr",
        "glm_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "glm_api_key": "test-key",
        "glm_asr_model": "glm-asr-2512",
        "asr_max_duration_seconds": 1800,
    }
    base.update(overrides)
    return Settings(**base)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or ""

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def with_ffmpeg(monkeypatch):
    # provider __init__ 会检查 ffmpeg 是否存在;测试环境统一假装有。
    monkeypatch.setattr(asr_mod.shutil, "which", lambda name: "/usr/bin/ffmpeg")


# —— provider 路由 ——

def test_build_provider_returns_glm(with_ffmpeg):
    provider = build_asr_provider(_settings())
    assert isinstance(provider, GlmAsrASRProvider)


def test_build_provider_missing_key_raises(with_ffmpeg):
    with pytest.raises(ASRError, match="GLM API Key"):
        build_asr_provider(_settings(glm_api_key=""))


def test_build_provider_still_supports_tencent(with_ffmpeg):
    settings = _settings(
        asr_provider="tencent_rec_task",
        tencent_asr_secret_id="a",
        tencent_asr_secret_key="b",
        tencent_cos_secret_id="c",
        tencent_cos_secret_key="d",
        tencent_cos_bucket="e",
    )
    assert isinstance(build_asr_provider(settings), TencentRecTaskASRProvider)


# —— 分段转写 + 拼接 ——

def test_transcribe_video_url_joins_chunks(with_ffmpeg, monkeypatch):
    monkeypatch.setattr(asr_mod, "download_video", lambda settings, url, path: None)
    monkeypatch.setattr(asr_mod, "probe_media_streams", lambda path: {"types": ["audio", "video"], "codecs": ["aac", "h264"]})
    monkeypatch.setattr(asr_mod, "probe_duration", lambda path: 65.0)
    monkeypatch.setattr(asr_mod, "extract_audio", lambda video, audio: None)
    monkeypatch.setattr(asr_mod, "split_audio_chunks", lambda audio, out, secs: [Path("chunk_0000.mp3"), Path("chunk_0001.mp3"), Path("chunk_0002.mp3")])
    monkeypatch.setattr(GlmAsrASRProvider, "_transcribe_chunk", lambda self, path: (f"seg[{path.name}]", "req-id"))

    progress: list[str] = []
    provider = GlmAsrASRProvider(_settings())
    result = provider.transcribe_video_url("http://v/1.mp4", source_id="note-1", on_progress=progress.append)

    assert result.text == "seg[chunk_0000.mp3]\nseg[chunk_0001.mp3]\nseg[chunk_0002.mp3]"
    assert result.duration_seconds == 65.0
    assert result.provider == "glm_asr"
    # 多段时逐段回报进度心跳。
    assert progress == ["识别中…第 1/3 段", "识别中…第 2/3 段", "识别中…第 3/3 段"]


def test_transcribe_video_url_no_audio_raises(with_ffmpeg, monkeypatch):
    monkeypatch.setattr(asr_mod, "download_video", lambda settings, url, path: None)
    monkeypatch.setattr(asr_mod, "probe_media_streams", lambda path: {"types": ["video"], "codecs": ["h264"]})
    provider = GlmAsrASRProvider(_settings())
    with pytest.raises(ASRError, match="不包含音频流"):
        provider.transcribe_video_url("http://v/cover.mp4")


def test_transcribe_video_url_over_max_duration_raises(with_ffmpeg, monkeypatch):
    monkeypatch.setattr(asr_mod, "download_video", lambda settings, url, path: None)
    monkeypatch.setattr(asr_mod, "probe_media_streams", lambda path: {"types": ["audio"], "codecs": ["aac"]})
    monkeypatch.setattr(asr_mod, "probe_duration", lambda path: 99999.0)
    provider = GlmAsrASRProvider(_settings(asr_max_duration_seconds=1800))
    with pytest.raises(ASRError, match="超过 ASR 上限"):
        provider.transcribe_video_url("http://v/long.mp4")


# —— 单段 HTTP 调用:请求构造 + 响应解析 ——

def test_transcribe_chunk_posts_and_parses_text(with_ffmpeg, monkeypatch, tmp_path):
    chunk = tmp_path / "chunk_0000.mp3"
    chunk.write_bytes(b"ID3fake-mp3-bytes")
    captured: dict = {}

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        captured["files_keys"] = list((files or {}).keys())
        return _FakeResponse(200, {"id": "req-42", "text": "  你好世界  "})

    monkeypatch.setattr(asr_mod.httpx, "post", fake_post)
    provider = GlmAsrASRProvider(_settings())
    text, req_id = provider._transcribe_chunk(chunk)

    assert text == "你好世界"  # 前后空白被 strip
    assert req_id == "req-42"
    assert captured["url"] == "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["data"] == {"model": "glm-asr-2512"}
    assert captured["files_keys"] == ["file"]


def test_transcribe_chunk_4xx_fails_fast(with_ffmpeg, monkeypatch, tmp_path):
    chunk = tmp_path / "chunk_0000.mp3"
    chunk.write_bytes(b"fake")
    calls = {"n": 0}

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        calls["n"] += 1
        return _FakeResponse(400, text='{"error":"bad request"}')

    monkeypatch.setattr(asr_mod.httpx, "post", fake_post)
    provider = GlmAsrASRProvider(_settings())
    with pytest.raises(ASRError, match="HTTP 400"):
        provider._transcribe_chunk(chunk)
    assert calls["n"] == 1  # 4xx 不重试


def test_transcribe_chunk_network_error_retries(with_ffmpeg, monkeypatch, tmp_path):
    chunk = tmp_path / "chunk_0000.mp3"
    chunk.write_bytes(b"fake")
    calls = {"n": 0}

    def fake_post(url, headers=None, data=None, files=None, timeout=None):
        calls["n"] += 1
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(asr_mod.httpx, "post", fake_post)
    monkeypatch.setattr(asr_mod.time, "sleep", lambda s: None)  # 不真睡,加速
    provider = GlmAsrASRProvider(_settings())
    with pytest.raises(ASRError, match="已重试"):
        provider._transcribe_chunk(chunk)
    assert calls["n"] == asr_mod.GLM_ASR_MAX_RETRIES
