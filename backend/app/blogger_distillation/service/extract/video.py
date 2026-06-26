"""视频直链提取:从 TikHub 详情里挑码率最优的视频流、规范成 https、按编码 / 清晰度打分排序,并判断 URL 是不是视频 / 字幕。"""

from __future__ import annotations

from typing import Any
import httpx
from app.blogger_distillation.tikhub_client import first_int
from app.blogger_distillation.tikhub_client import recursive_find


# 选流编码偏好:同体积下 h265 最省,其次 av1,最后 h264。
_CODEC_PRIORITY = {"h265": 0, "av1": 1, "h264": 2}


def to_https(url: str) -> str:
    """把 http:// 直链升到 https://。实测同一 CDN 文件 https 比 http(80) 快约 3 倍(跨境回源)。"""
    if isinstance(url, str) and url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def pick_video_stream(raw: dict[str, Any]) -> dict[str, Any] | None:
    """从 video.media.stream 选最省流的码流:体积最小优先,同体积偏 h265,并强制 https。

    返回 {url, size, codec, bitrate, width, height};无可用码流返回 None。
    """
    video = recursive_find(raw, "video")
    if not isinstance(video, dict):
        return None
    stream = (video.get("media") or {}).get("stream") or video.get("stream") or {}
    if not isinstance(stream, dict):
        return None
    options: list[dict[str, Any]] = []
    for codec in ("h265", "av1", "h264"):
        items = stream.get(codec)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = ""
            for key in ("masterUrl", "master_url", "main_url", "mainUrl", "url"):
                value = item.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    url = value
                    break
            if not url:
                for key in ("backupUrls", "backup_urls", "backupUrl", "backup_url"):
                    value = item.get(key)
                    if isinstance(value, list):
                        url = next((u for u in value if isinstance(u, str) and u.startswith("http")), "")
                    elif isinstance(value, str):
                        url = value
                    if url:
                        break
            if not url or not is_likely_video_url(url):
                continue
            options.append(
                {
                    "url": to_https(url),
                    "size": first_int(item, ["size", "video_size", "videoSize"]),
                    "codec": codec,
                    "bitrate": first_int(item, ["videoBitrate", "video_bitrate", "bitrate", "avgBitrate"]),
                    "width": first_int(item, ["width"]),
                    "height": first_int(item, ["height"]),
                }
            )
    if not options:
        return None

    def sort_key(option: dict[str, Any]) -> tuple[int, int, int]:
        size = option["size"] if option["size"] > 0 else 1 << 62
        bitrate = option["bitrate"] if option["bitrate"] > 0 else 1 << 30
        return (size, bitrate, _CODEC_PRIORITY.get(option["codec"], 9))

    options.sort(key=sort_key)
    return options[0]


def probe_remote_size(url: str) -> int:
    """HEAD 探测远端文件字节数;失败返回 0。仅用于给用户展示「视频大小」提示。"""
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 PubSync/1.0"}) as client:
            response = client.head(to_https(url))
            length = response.headers.get("content-length", "")
        return int(length) if length.isdigit() else 0
    except Exception:
        return 0


def extract_video_url(raw: dict[str, Any]) -> str:
    best = pick_video_stream(raw)
    if best:
        return best["url"]
    video = recursive_find(raw, "video")
    if isinstance(video, dict):
        for url in extract_stream_urls(video):
            if is_likely_video_url(url):
                return to_https(url)
        for key in ("videoUrl", "video_url", "play_url", "playUrl"):
            value = recursive_find(video, key)
            if is_likely_video_url(value):
                return to_https(value)
    candidates = collect_video_url_candidates(raw)
    if candidates:
        return to_https(candidates[0])
    return ""


def extract_stream_urls(video: dict[str, Any]) -> list[str]:
    stream = ((video.get("media") or {}).get("stream") or video.get("stream") or {})
    if not isinstance(stream, dict):
        return []
    urls: list[str] = []
    for codec in ("h264", "h265", "av1"):
        items = stream.get(codec)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for key in ("masterUrl", "master_url", "main_url", "mainUrl", "url"):
                value = item.get(key)
                if isinstance(value, str):
                    urls.append(value)
            for key in ("backupUrls", "backup_urls", "backupUrl", "backup_url"):
                value = item.get(key)
                if isinstance(value, list):
                    urls.extend(url for url in value if isinstance(url, str))
                elif isinstance(value, str):
                    urls.append(value)
    return urls


def is_likely_video_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("http"):
        return False
    lowered = value.lower()
    if is_non_video_media_url(lowered):
        return False
    video_markers = (".mp4", ".mov", ".m3u8", ".ts", "video", "stream", "play", "sns-video")
    return any(marker in lowered for marker in video_markers)


def is_video_url_candidate(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("http"):
        return False
    return not is_non_video_media_url(value.lower())


def collect_video_url_candidates(raw: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, (*path, str(key)))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))
            return
        if not isinstance(value, str) or not value.startswith("http"):
            return
        lowered = value.lower()
        if is_non_video_media_url(lowered):
            return
        path_text = ".".join(path).lower()
        if is_subtitle_path(path_text):
            return
        if any(marker in path_text for marker in ("video", "stream", "play", "master", "m3u8", "h264", "h265")):
            if value not in seen:
                seen.add(value)
                candidates.append(value)

    visit(raw, ())
    return sorted(candidates, key=video_url_score, reverse=True)


def is_non_video_media_url(lowered_url: str) -> bool:
    image_markers = (".jpg", ".jpeg", ".png", ".webp", ".gif", "imageview", "image")
    subtitle_markers = (".srt", ".vtt", "subtitle", "caption", "subrip", "danmaku")
    return any(marker in lowered_url for marker in (*image_markers, *subtitle_markers))


def is_subtitle_path(path_text: str) -> bool:
    return any(marker in path_text for marker in ("subtitle", "caption", "subrip", "srt", "vtt", "danmaku"))


def video_url_score(url: str) -> int:
    lowered = url.lower()
    score = 0
    for marker in (".mp4", ".m3u8", "h264", "h265", "video", "stream", "play"):
        if marker in lowered:
            score += 10
    if "sns-video" in lowered:
        score += 20
    return score
