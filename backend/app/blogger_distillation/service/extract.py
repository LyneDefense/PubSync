"""Post normalization and media/subtitle extraction helpers (no DB orchestration)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation.tikhub_client import (
    TikHubDouyinClient,
    TikHubXhsClient,
    XhsPostCandidate,
    first_int,
    first_str,
    parse_timestamp,
    recursive_find,
    unwrap_payload,
)
from app.models import BloggerPost, BloggerProfile

logger = logging.getLogger(__name__)


def normalize_post(candidate: XhsPostCandidate, detail_payload: dict[str, Any]) -> dict[str, Any]:
    payload = unwrap_payload(detail_payload)
    raw = normalize_detail_payload(payload, detail_payload)
    counts = merge_interaction_counts(raw, candidate)
    hashtags = extract_hashtags(raw)
    media_urls = extract_media_urls(raw)
    video_url = extract_video_url(raw) or extract_video_url(detail_payload)
    if video_url and video_url not in media_urls:
        media_urls.insert(0, video_url)
    title = first_str(raw, ["title", "display_title", "note_title"]) or first_str(candidate.raw, ["display_title", "title"])
    body = first_str(raw, ["desc", "description", "content", "note_desc", "text"])
    url = first_str(raw, ["share_url", "url", "web_url"]) or first_str(candidate.raw, ["share_url", "url"])
    published_at = parse_timestamp(
        recursive_find(raw, "time") or recursive_find(raw, "timestamp") or recursive_find(raw, "last_update_time")
    )
    like_count = counts["like_count"]
    favorite_count = counts["favorite_count"]
    comment_count = counts["comment_count"]
    share_count = counts["share_count"]
    score = like_count * 0.35 + favorite_count * 0.45 + comment_count * 0.2 + share_count * 0.05
    return {
        "external_id": candidate.external_id,
        "url": url,
        "title": title[:500] or "未命名笔记",
        "body_text": body,
        "content_type": "video" if candidate.note_type == "video" or video_url else "image",
        "hashtags_json": json.dumps(hashtags, ensure_ascii=False),
        "cover_url": media_urls[0] if media_urls else "",
        "media_urls_json": json.dumps(media_urls, ensure_ascii=False),
        "transcript_text": "",
        "asr_status": "pending" if candidate.note_type == "video" else "not_required",
        "asr_error": "",
        "published_at": published_at,
        "like_count": like_count,
        "favorite_count": favorite_count,
        "comment_count": comment_count,
        "share_count": share_count,
        "score": score,
        "raw_json": json.dumps(detail_payload, ensure_ascii=False, default=str),
    }


def normalize_detail_payload(payload: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            note_card = first.get("noteCard") or first.get("note_card") or first.get("note")
            if isinstance(note_card, dict):
                merged = dict(note_card)
                for key in ("id", "note_id", "xsecToken", "xsec_token"):
                    if key in first and key not in merged:
                        merged[key] = first[key]
                return merged
            return first
    if isinstance(payload, dict):
        note_card = payload.get("noteCard") or payload.get("note_card") or payload.get("note")
        if isinstance(note_card, dict):
            merged = dict(note_card)
            for key in ("id", "note_id", "xsecToken", "xsec_token"):
                if key in payload and key not in merged:
                    merged[key] = payload[key]
            return merged
        return payload
    return fallback


def supplement_video_detail_with_url(client: TikHubXhsClient | TikHubDouyinClient, candidate: XhsPostCandidate, fallback: dict[str, Any]) -> dict[str, Any]:
    for detail in client.get_video_note_detail_variants(candidate):
        if extract_video_url(detail):
            logger.info("视频 URL 补取成功：note_id=%s，端点=%s", candidate.external_id, detail.get("_endpoint_used", "<unknown>"))
            return detail
    return fallback


def merge_interaction_counts(raw: dict[str, Any], candidate: XhsPostCandidate) -> dict[str, int]:
    detail_counts = extract_counts_from_payload(raw)
    return {
        "like_count": detail_counts["like_count"] or candidate.like_count,
        "favorite_count": detail_counts["favorite_count"] or candidate.favorite_count,
        "comment_count": detail_counts["comment_count"] or candidate.comment_count,
        "share_count": detail_counts["share_count"] or candidate.share_count,
    }


def extract_counts_from_payload(raw: dict[str, Any]) -> dict[str, int]:
    interact = recursive_find(raw, "interact_info") or recursive_find(raw, "interactInfo")
    sources = collect_metric_sources(raw, interact)
    return {
        "like_count": first_positive_count(sources, ["liked_count", "liked_count_str", "likedCount", "like_count", "likeCount", "likes", "likeNum"]),
        "favorite_count": first_positive_count(
            sources,
            ["collected_count", "collected_count_str", "collectedCount", "favorite_count", "collect_count", "collects", "collectNum"],
        ),
        "comment_count": first_positive_count(
            sources,
            ["comment_count", "comment_count_str", "commentCount", "commentCountStr", "comments", "comment_num", "commentNum", "note_comment_count"],
        ),
        "share_count": first_positive_count(sources, ["share_count", "share_count_str", "shareCount", "sharedCount", "shares", "shareNum"]),
    }


def collect_metric_sources(raw: dict[str, Any], primary: Any | None = None) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add(value: Any) -> None:
        if not isinstance(value, dict) or id(value) in seen:
            return
        seen.add(id(value))
        sources.append(value)

    add(primary)
    for key in ("interact_info", "interactInfo", "note_card", "noteCard", "note", "stats", "statistics"):
        value = recursive_find(raw, key)
        add(value)
    add(raw)
    return sources


def first_positive_count(sources: list[dict[str, Any]], keys: list[str]) -> int:
    for source in sources:
        count = first_int(source, keys)
        if count > 0:
            return count
    return 0


def normalize_comment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": first_str(item, ["content", "text", "comment_content", "desc"]),
        "like_count": first_int(item, ["like_count", "liked_count", "digg_count", "likes"]),
        "created_at": str(parse_timestamp(item.get("create_time") or item.get("time")) or ""),
    }


def upsert_post(db: Session, tenant_id: int, blogger: BloggerProfile, data: dict[str, Any]) -> BloggerPost:
    post = db.scalar(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger.id,
            BloggerPost.external_id == data["external_id"],
        )
    )
    if not post:
        post = BloggerPost(tenant_id=tenant_id, blogger_id=blogger.id, platform=blogger.platform, **data)
        db.add(post)
        db.flush()
        return post
    for key, value in data.items():
        setattr(post, key, value)
    db.flush()
    return post


def extract_hashtags(raw: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    for key in ("tag_list", "hash_tag", "hashtags", "tags"):
        value = recursive_find(raw, key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    tags.add(item.lstrip("#"))
                elif isinstance(item, dict):
                    tag = first_str(item, ["name", "tag_name", "title"])
                    if tag:
                        tags.add(tag.lstrip("#"))
    text = " ".join([first_str(raw, ["title", "desc", "content"]), json.dumps(raw, ensure_ascii=False)[:2000]])
    for tag in re.findall(r"#([\w\u4e00-\u9fff-]+)", text):
        tags.add(tag)
    return sorted(tags)[:20]


def extract_media_urls(raw: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"url", "trace_id", "file_id"} and isinstance(child, str) and child.startswith("http"):
                    urls.append(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for key in ("image_list", "images_list", "images", "cover", "image"):
        value = recursive_find(raw, key)
        if value:
            visit(value)
    seen: set[str] = set()
    deduped = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped[:12]


def extract_video_url(raw: dict[str, Any]) -> str:
    video = recursive_find(raw, "video")
    if isinstance(video, dict):
        for url in extract_stream_urls(video):
            if is_likely_video_url(url):
                return url
        for key in ("videoUrl", "video_url", "play_url", "playUrl"):
            value = recursive_find(video, key)
            if is_likely_video_url(value):
                return value
    candidates = collect_video_url_candidates(raw)
    if candidates:
        return candidates[0]
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


def extract_subtitle_url(raw: dict[str, Any]) -> str:
    candidates: list[str] = []

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
            candidates.append(value)

    visit(raw, ())
    return candidates[0] if candidates else ""


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
