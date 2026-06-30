"""笔记 / 评论的规范化与入库:把 TikHub 详情 payload 规范成 BloggerPost 字段、合并互动数、提取话题 / 图片,以及 upsert_post 落库。视频直链与字幕的底层提取分别在 .video / .subtitle。"""

from __future__ import annotations

import logging
import json
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.blogger_distillation.tikhub_client import TikHubDouyinClient
from app.blogger_distillation.tikhub_client import TikHubXhsClient
from app.blogger_distillation.tikhub_client import XhsPostCandidate
from app.blogger_distillation.tikhub_client import first_int
from app.blogger_distillation.tikhub_client import first_str
from app.blogger_distillation.tikhub_client import parse_timestamp
from app.blogger_distillation.tikhub_client import recursive_find
from app.blogger_distillation.tikhub_client import unwrap_payload
from app.models import BloggerPost
from app.models import BloggerProfile
from .video import extract_video_url

logger = logging.getLogger(__name__)


def extract_note_key(raw: dict[str, Any], detail_payload: dict[str, Any], fallback: str) -> str:
    """稳定规范键:小红书 biz_id、抖音 aweme_id。note_id 会随端点漂移,这个跨次稳定;取不到则回退 note_id。"""
    for source in (raw, detail_payload):
        if not isinstance(source, dict):
            continue
        for key in ("biz_id", "bizId", "aweme_id", "awemeId"):
            value = recursive_find(source, key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return fallback


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
        "note_key": extract_note_key(raw, detail_payload, candidate.external_id),
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


def resolve_note_card(container: dict[str, Any]) -> dict[str, Any]:
    """从详情容器里取出真正的「笔记卡」。兼容三种壳:
    - app_v2 / web_v3:`noteCard` / `note_card` / `note`(dict);
    - app/get_note_info:`note_list` / `notes`(list,取第 0 条)—— 这层壳之前没处理,
      导致图文笔记的 `desc` 不在容器顶层,`first_str` 取不到 → body_text 全空。
    取到子卡后,把外层的 id / token 并进来(子卡可能缺这些)。都没有则原样返回容器。"""
    note_card = container.get("noteCard") or container.get("note_card") or container.get("note")
    if not isinstance(note_card, dict):
        for list_key in ("note_list", "notes"):
            seq = container.get(list_key)
            if isinstance(seq, list) and seq and isinstance(seq[0], dict):
                note_card = seq[0]
                break
    if not isinstance(note_card, dict):
        return container
    merged = dict(note_card)
    for key in ("id", "note_id", "xsecToken", "xsec_token"):
        if key in container and key not in merged:
            merged[key] = container[key]
    return merged


def normalize_detail_payload(payload: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            return resolve_note_card(first)
    if isinstance(payload, dict):
        return resolve_note_card(payload)
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
    # 权威去重按 note_key(biz_id,跨端点稳定);取不到再回退 external_id(note_id)。
    note_key = (data.get("note_key") or "").strip()
    post = None
    if note_key:
        post = db.scalar(
            select(BloggerPost).where(
                BloggerPost.tenant_id == tenant_id,
                BloggerPost.blogger_id == blogger.id,
                BloggerPost.note_key == note_key,
            )
        )
    if not post:
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
