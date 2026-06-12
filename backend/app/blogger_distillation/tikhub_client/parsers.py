"""Pure parsing / normalization helpers for TikHub responses (no HTTP)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.blogger_distillation.tikhub_client.base import TikHubError, XhsPostCandidate


def unwrap_payload(data: Any) -> Any:
    current = data
    for _ in range(4):
        if isinstance(current, dict):
            for key in ("data", "result", "note", "notes", "items"):
                value = current.get(key)
                if value not in (None, "", []):
                    current = value
                    break
            else:
                return current
        else:
            return current
    return current


def first_str(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int)):
            return str(value).strip()
    return ""


def first_int(data: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            normalized = parse_count(value)
            if normalized is not None:
                return normalized
    return 0


def parse_count(value: str) -> int | None:
    text = value.replace(",", "").strip()
    if not text:
        return None
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10_000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def parse_xhs_profile_link(homepage_url: str) -> dict[str, str]:
    raw = homepage_url.strip().rstrip("。.,，；;")
    parsed = urlparse(raw)
    path = parsed.path or raw
    match = re.search(r"/user/profile/([^/?#]+)", path)
    if not match:
        raise TikHubError("请输入小红书博主主页链接，格式应为 https://www.xiaohongshu.com/user/profile/{user_id}")
    query = parse_qs(parsed.query)
    return {
        "share_text": raw,
        "user_id": match.group(1),
        "xsec_token": (query.get("xsec_token") or [""])[0],
    }


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


def dig(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def extract_note_page(payload: dict[str, Any]) -> dict[str, Any]:
    page = find_best_note_container(payload)
    if page is None:
        return {"notes": [], "next_cursor": "", "has_more": False}
    notes = [normalize_feed_item(item) for item in extract_container_items(page)]
    notes = [item for item in notes if first_str(item, ["note_id", "id", "noteId", "display_title", "title"])]
    note_ids = collect_note_ids(notes)
    return {
        "notes": notes,
        "next_cursor": find_container_cursor(page, note_ids) or find_payload_page_cursor(payload, note_ids),
        "has_more": first_bool(page, HAS_MORE_KEYS) or first_bool_recursive(payload, HAS_MORE_KEYS),
    }


HAS_MORE_KEYS = ("has_more", "hasMore", "has_more_note", "hasMoreNote", "has_next", "hasNext")
CURSOR_KEYS = (
    "next_cursor",
    "nextCursor",
    "next_page_cursor",
    "nextPageCursor",
    "cursor",
    "lastCursor",
    "last_cursor",
    "cursor_id",
    "cursorId",
)
PAGE_CURSOR_KEYS = tuple(key for key in CURSOR_KEYS if key != "cursor")


def score_note_page(page_data: dict[str, Any], requested_count: int) -> int:
    note_count = len(page_data["notes"])
    score = note_count
    if note_count >= requested_count:
        score += 100
    if page_data["has_more"]:
        score += 500
    if page_data["next_cursor"]:
        score += 1000
    return score


def find_best_note_container(value: Any) -> dict[str, Any] | None:
    candidates: list[tuple[int, dict[str, Any]]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            items = extract_container_items(node)
            normalized = [normalize_feed_item(item) for item in items]
            note_count = sum(1 for item in normalized if first_str(item, ["note_id", "id", "noteId", "display_title", "title"]))
            if note_count:
                cursor_bonus = 2 if any(key in node for key in ("cursor", "next_cursor", "nextCursor", "lastCursor", "has_more", "hasMore")) else 0
                candidates.append((note_count * 10 + cursor_bonus, node))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def extract_container_items(container: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "notes", "feeds", "list"):
        value = container.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def normalize_feed_item(item: dict[str, Any]) -> dict[str, Any]:
    note = item.get("noteCard") or item.get("note_card") or item.get("note")
    if isinstance(note, dict):
        merged = dict(note)
        for key in ("id", "note_id", "noteId", "xsecToken", "xsec_token", "xsec_source", "cursor", "type"):
            if item.get(key) not in (None, "", [], {}) and key not in merged:
                merged[key] = item[key]
        xsec_token = extract_xsec_token(item)
        if xsec_token and not extract_xsec_token(merged):
            merged["xsecToken"] = xsec_token
        return merged
    return item


def extract_xsec_token(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    direct = first_str(value, ["xsec_token", "xsecToken", "xsec_source"])
    if direct:
        return direct
    for key in ("noteCard", "note_card", "note", "user", "user_info"):
        nested = value.get(key)
        if isinstance(nested, dict):
            token = extract_xsec_token(nested)
            if token:
                return token
    return ""


def find_container_cursor(container: dict[str, Any], note_ids: set[str]) -> str:
    for key in CURSOR_KEYS:
        cursor = clean_page_cursor(container.get(key), note_ids)
        if cursor:
            return cursor
    return ""


def find_payload_page_cursor(payload: dict[str, Any], note_ids: set[str]) -> str:
    def visit(node: Any) -> str:
        if isinstance(node, dict):
            if is_note_like_cursor_node(node):
                return ""
            for key in PAGE_CURSOR_KEYS:
                cursor = clean_page_cursor(node.get(key), note_ids)
                if cursor:
                    return cursor
            for child in node.values():
                cursor = visit(child)
                if cursor:
                    return cursor
        elif isinstance(node, list):
            for child in node:
                cursor = visit(child)
                if cursor:
                    return cursor
        return ""

    return visit(payload)


def is_note_like_cursor_node(node: dict[str, Any]) -> bool:
    if any(key in node for key in ("items", "notes", "feeds", "list")):
        return False
    return any(key in node for key in ("noteCard", "note_card", "note", "note_id", "noteId", "display_title", "title"))


def clean_page_cursor(value: Any, note_ids: set[str]) -> str:
    if not isinstance(value, (str, int)):
        return ""
    cursor = str(value).strip()
    if not cursor or cursor in note_ids:
        return ""
    return cursor


def collect_note_ids(notes: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for note in notes:
        for key in ("note_id", "id", "noteId", "note_id_str"):
            value = note.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                ids.add(str(value).strip())
    return ids


def extract_interaction_counts(value: dict[str, Any]) -> dict[str, int]:
    interact = recursive_find(value, "interact_info") or recursive_find(value, "interactInfo")
    sources = collect_metric_sources(value, interact)
    return {
        "like_count": first_count(sources, ["liked_count", "liked_count_str", "likedCount", "like_count", "likeCount", "likes", "likeNum"]),
        "favorite_count": first_count(
            sources,
            ["collected_count", "collected_count_str", "collectedCount", "favorite_count", "collect_count", "collects", "collectNum"],
        ),
        "comment_count": first_count(
            sources,
            ["comment_count", "comment_count_str", "commentCount", "commentCountStr", "comments", "comment_num", "commentNum", "note_comment_count"],
        ),
        "share_count": first_count(sources, ["share_count", "share_count_str", "shareCount", "sharedCount", "shares", "shareNum"]),
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


def first_count(sources: list[dict[str, Any]], keys: list[str]) -> int:
    for source in sources:
        count = first_int(source, keys)
        if count > 0:
            return count
    return 0


def first_bool(data: dict[str, Any], keys: list[str]) -> bool:
    for key in keys:
        value = data.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n", ""}:
                return False
    return False


def first_bool_recursive(data: Any, keys: tuple[str, ...]) -> bool:
    if isinstance(data, dict):
        if first_bool(data, list(keys)):
            return True
        return any(first_bool_recursive(child, keys) for child in data.values())
    if isinstance(data, list):
        return any(first_bool_recursive(child, keys) for child in data)
    return False


def find_note_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_note_page(payload)["notes"]


def find_comment_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lists = find_lists(payload)
    comment_lists = [
        items
        for items in lists
        if items
        and isinstance(items[0], dict)
        and any(key in items[0] for key in ("content", "text", "comment_content", "like_count", "liked_count"))
    ]
    if not comment_lists:
        return []
    return max(comment_lists, key=len)


def find_lists(value: Any) -> list[list[dict[str, Any]]]:
    found: list[list[dict[str, Any]]] = []
    if isinstance(value, list):
        dict_items = [item for item in value if isinstance(item, dict)]
        if dict_items:
            found.append(dict_items)
        for item in value:
            found.extend(find_lists(item))
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(find_lists(child))
    return found


def find_cursor(payload: dict[str, Any]) -> str:
    for key in CURSOR_KEYS:
        value = recursive_find(payload, key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return ""


def find_index(payload: dict[str, Any]) -> int:
    value = recursive_find(payload, "index")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def find_page_area(payload: dict[str, Any]) -> str:
    value = recursive_find(payload, "pageArea") or recursive_find(payload, "page_area")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def recursive_find(value: Any, target_key: str) -> Any:
    if isinstance(value, dict):
        if target_key in value:
            return value[target_key]
        for child in value.values():
            result = recursive_find(child, target_key)
            if result not in (None, "", []):
                return result
    elif isinstance(value, list):
        for child in value:
            result = recursive_find(child, target_key)
            if result not in (None, "", []):
                return result
    return None


def find_user_id(payload: dict[str, Any]) -> str:
    for key in ("user_id", "userId", "userid", "id"):
        value = recursive_find(payload, key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return ""


def detect_note_type(note: dict[str, Any]) -> str:
    value = first_str(note, ["type", "note_type", "noteType", "modelType"]).lower()
    if "video" in value:
        return "video"
    nested = recursive_find(note, "type")
    if isinstance(nested, str) and "video" in nested.lower():
        return "video"
    return "image"


def parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, int):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None
