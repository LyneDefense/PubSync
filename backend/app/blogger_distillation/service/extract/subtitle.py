"""字幕 / ASR 文本处理:找字幕直链、下载解析(srt/vtt/json)、口播转写文本归一(去时间轴、中文占比判断)。"""

from __future__ import annotations

import re
from typing import Any
import httpx
from .video import is_subtitle_path
from .video import to_https


def extract_subtitle_urls(raw: dict[str, Any]) -> list[str]:
    """收集所有字幕轨 URL(小红书常挂中/英多条),去重保序。由调用方逐个取、挑中文那条。"""
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
        path_text = ".".join(path).lower()
        lowered = value.lower()
        if is_subtitle_path(path_text) or any(marker in lowered for marker in (".srt", ".vtt", "subtitle", "caption")):
            url = to_https(value)
            if url not in seen:
                seen.add(url)
                candidates.append(url)

    visit(raw, ())
    return candidates


def extract_subtitle_url(raw: dict[str, Any]) -> str:
    urls = extract_subtitle_urls(raw)
    return urls[0] if urls else ""


def fetch_subtitle_text(subtitle_url: str) -> str:
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 PubSync/1.0"}) as client:
        response = client.get(subtitle_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        text = response.text
    if "json" in content_type:
        try:
            return extract_text_from_subtitle_json(response.json())
        except ValueError:
            pass
    return parse_subtitle_text(text)


def extract_text_from_subtitle_json(value: Any) -> str:
    fragments: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key.lower() in {"text", "content", "sentence", "word"} and isinstance(child, str):
                    fragments.append(child.strip())
                else:
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return normalize_transcript_text("\n".join(fragment for fragment in fragments if fragment))


def parse_subtitle_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("WEBVTT"):
            continue
        if stripped.isdigit() or "-->" in stripped:
            continue
        if re.match(r"^(NOTE|STYLE|REGION)\b", stripped, flags=re.IGNORECASE):
            continue
        lines.append(re.sub(r"<[^>]+>", "", stripped))
    return normalize_transcript_text("\n".join(lines))


def normalize_transcript_text(text: str) -> str:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def is_mostly_chinese(text: str, *, threshold: float = 0.2) -> bool:
    """转写是否以中文为主。小红书会挂自动翻译的英文字幕,用它过滤掉非中文字幕。

    阈值按「中文字符 / 中英文字符总数」算,中文视频正常 >0.5;纯英文字幕≈0。
    """
    sample = (text or "")[:2000]
    han = sum(1 for ch in sample if "一" <= ch <= "鿿")
    latin = sum(1 for ch in sample if ch.isascii() and ch.isalpha())
    if han + latin == 0:
        return False
    return han / (han + latin) >= threshold


def strip_asr_timestamps(text: str) -> str:
    """清掉腾讯 ASR 文本里的 [0:0.000,1:0.220] 这类时间戳标记。"""
    return re.sub(r"\[\d+:\d+\.\d+,\d+:\d+\.\d+\]\s*", "", text or "").strip()
