"""VideoFetcher:ASR 与拍法抽帧共用一次视频下载(懒下载 + 缓存 + 失败降级)。"""

import app.blogger_distillation.asr as asr_mod
from app.blogger_distillation.asr import ASRError, VideoFetcher


def test_downloads_once_and_caches(monkeypatch, tmp_path):
    calls = []

    def fake_download(settings, url, dest):
        calls.append(url)
        dest.write_bytes(b"video")

    monkeypatch.setattr(asr_mod, "download_video", fake_download)
    fetcher = VideoFetcher(settings=None, dest_dir=tmp_path)
    p1 = fetcher.get("http://v/1.mp4")
    p2 = fetcher.get("http://v/1.mp4")  # 第二个消费者(抽帧)
    assert p1 is not None and p1 == p2
    assert len(calls) == 1  # 只下一次,第二次复用缓存


def test_failure_returns_none_no_retry(monkeypatch, tmp_path):
    calls = []

    def fake_download(settings, url, dest):
        calls.append(url)
        raise ASRError("下载失败")

    monkeypatch.setattr(asr_mod, "download_video", fake_download)
    fetcher = VideoFetcher(settings=None, dest_dir=tmp_path)
    assert fetcher.get("http://v/1.mp4") is None
    assert fetcher.get("http://v/1.mp4") is None  # 失败缓存,不反复重试
    assert len(calls) == 1


def test_empty_url_skips_download(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(asr_mod, "download_video", lambda *a: calls.append(1))
    assert VideoFetcher(settings=None, dest_dir=tmp_path).get("") is None
    assert not calls  # 没 URL 根本不下
