"""抖音响应解析:主页链接、用户信息、视频详情 / 列表项归一、评论提取、URL model 取直链。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse
from app.blogger_distillation.tikhub_client.base import XhsPostCandidate
from .common import dig
from .common import first_int
from .common import first_str


def parse_douyin_profile_link(homepage_url: str) -> str:
    raw = homepage_url.strip().rstrip("。.,，；;")
    parsed = urlparse(raw)
    path = parsed.path or raw
    match = re.search(r"/user/([^/?#]+)", path)
    return match.group(1) if match else raw


def normalize_douyin_user_info(payload: dict[str, Any]) -> dict[str, Any]:
    data = dig(payload, "data", "data", default=None) or dig(payload, "data", default={})
    if isinstance(data, dict):
        user = data.get("user") or data.get("user_info") or data
    else:
        user = {}
    if not isinstance(user, dict):
        user = {}
    avatar = user.get("avatar_thumb") or user.get("avatar_medium") or user.get("avatar") or ""
    if isinstance(avatar, dict):
        url_list = avatar.get("url_list") or []
        avatar = url_list[0] if url_list else ""
    return {
        "id": first_str(user, ["sec_uid", "secUid", "uid", "user_id", "userId"]),
        "nickname": first_str(user, ["nickname", "name"]),
        "avatar": avatar if isinstance(avatar, str) else "",
        "fans": str(first_int(user, ["follower_count", "fans_count", "fansCount"])),
        "description": first_str(user, ["signature", "bio", "desc"]),
        "unique_id": first_str(user, ["unique_id", "short_id"]),
    }


def extract_douyin_video_page(payload: dict[str, Any]) -> dict[str, Any]:
    data = dig(payload, "data", default={})
    if not isinstance(data, dict):
        data = {}
    raw_items = data.get("aweme_list") or data.get("list") or []
    items = [normalize_douyin_video_item(item) for item in raw_items if isinstance(item, dict)]
    items = [item for item in items if item.get("id")]
    return {
        "items": items,
        "has_more": bool(data.get("has_more", False)),
        "next_cursor": str(data.get("max_cursor", data.get("cursor", "")) or ""),
    }


def normalize_douyin_video_item(value: dict[str, Any]) -> dict[str, Any]:
    item = value.get("aweme_detail") if isinstance(value.get("aweme_detail"), dict) else value
    stat = item.get("statistics") or {}
    video = item.get("video") or {}
    author = item.get("author") or {}
    music = item.get("music") or {}
    cover_url = ""
    video_url = ""
    if isinstance(video, dict):
        cover_url = first_url_from_douyin_url_model(video.get("origin_cover")) or first_url_from_douyin_url_model(video.get("cover"))
        if not cover_url:
            cover_url = first_url_from_douyin_url_model(video.get("dynamic_cover"))
        video_url = first_url_from_douyin_url_model(video.get("play_addr_h264")) or first_url_from_douyin_url_model(video.get("play_addr"))
    tags = []
    for tag in item.get("text_extra") or []:
        if isinstance(tag, dict) and tag.get("hashtag_name"):
            tags.append(str(tag["hashtag_name"]))
    return {
        "id": first_str(item, ["aweme_id", "video_id", "id"]),
        "title": first_str(item, ["desc", "title"]),
        "cover": cover_url,
        "type": "video",
        "likes": str(first_int(stat, ["digg_count"])),
        "comments": str(first_int(stat, ["comment_count"])),
        "collects": str(first_int(stat, ["collect_count"])),
        "shares": str(first_int(stat, ["share_count"])),
        "plays": str(first_int(stat, ["play_count"])),
        "author_id": first_str(author, ["sec_uid", "uid"]),
        "author_name": first_str(author, ["nickname", "name"]),
        "create_time": str(item.get("create_time", "")),
        "video_url": video_url,
        "duration": str(video.get("duration", "")) if isinstance(video, dict) else "",
        "music_title": first_str(music, ["title"]) if isinstance(music, dict) else "",
        "tags": tags,
        "_raw_platform": "douyin",
        "_raw": item,
    }


def normalize_douyin_video_obj(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "desc": item.get("title", ""),
        "title": item.get("title", ""),
        "time": item.get("create_time", ""),
        "interactInfo": {
            "likedCount": item.get("likes", "0"),
            "commentCount": item.get("comments", "0"),
            "shareCount": item.get("shares", "0"),
            "collectedCount": item.get("collects", "0"),
            "playCount": item.get("plays", "0"),
        },
        "type": "video",
        "cover": item.get("cover", ""),
        "coverUrl": item.get("cover", ""),
        "videoUrl": item.get("video_url", ""),
        "video": {"play_url": item.get("video_url", "")},
        "imageList": [{"url": item.get("cover", "")}] if item.get("cover") else [],
        "tagList": [{"name": tag} for tag in item.get("tags", [])],
        "duration": item.get("duration", ""),
        "authorId": item.get("author_id", ""),
        "authorName": item.get("author_name", ""),
        "musicTitle": item.get("music_title", ""),
        "_raw": item.get("_raw", item),
    }


def normalize_douyin_detail_payload(payload: dict[str, Any], candidate: XhsPostCandidate) -> dict[str, Any]:
    data = dig(payload, "data", default={})
    if isinstance(data, dict):
        raw_item = data.get("aweme_detail") or data.get("data") or data
    else:
        raw_item = {}
    if not isinstance(raw_item, dict) or not first_str(raw_item, ["aweme_id", "video_id", "id", "desc", "title"]):
        raw_item = candidate.raw
    item = normalize_douyin_video_item(raw_item)
    if not item.get("id"):
        item["id"] = candidate.external_id
    if not item.get("title"):
        item["title"] = first_str(candidate.raw, ["title", "desc"])
    normalized = normalize_douyin_video_obj(item)
    normalized["_endpoint_used"] = payload.get("_endpoint_used", "")
    normalized["_endpoint_group"] = payload.get("_endpoint_group", "")
    normalized["_raw_detail"] = payload
    return normalized


def extract_douyin_comments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", payload)
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        return []
    comments = data.get("comments") or data.get("comment_list") or data.get("list") or data.get("items") or []
    if isinstance(comments, dict):
        comments = comments.get("list") or comments.get("comments") or []
    return comments if isinstance(comments, list) else []


def first_url_from_douyin_url_model(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    url_list = value.get("url_list") or value.get("urlList") or []
    if isinstance(url_list, list):
        for item in url_list:
            if isinstance(item, str) and item.startswith("http"):
                return item
    return first_str(value, ["url", "uri"])
