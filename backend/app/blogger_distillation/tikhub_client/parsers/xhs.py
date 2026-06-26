"""小红书响应解析:主页 / 笔记链接、笔记列表分页(容器定位 / 游标 / xsec_token)、互动数提取、笔记类型判定。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlparse
from app.blogger_distillation.tikhub_client.base import TikHubError
from .common import first_bool
from .common import first_bool_recursive
from .common import first_int
from .common import first_str
from .common import recursive_find


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


def parse_xhs_note_link(url: str) -> dict[str, str]:
    """从小红书笔记分享链接解析 note_id + xsec_token(链接可能裹在分享文案里)。

    支持 /explore/{id} 与 /discovery/item/{id};短链(xhslink.com)需调用方先展开为完整链接。
    """
    text = (url or "").strip()
    found = re.search(r"https?://[^\s，。;；）)]+", text)
    raw = (found.group(0) if found else text).rstrip("。.,，；;")
    parsed = urlparse(raw)
    match = re.search(r"/(?:explore|discovery/item)/([0-9a-zA-Z]+)", parsed.path)
    if not match:
        raise TikHubError("无法从链接解析笔记 ID，请粘贴小红书笔记的「分享链接」")
    token = (parse_qs(parsed.query).get("xsec_token") or [""])[0]
    return {"note_id": match.group(1), "xsec_token": token}


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
            [
                "comments_count",  # 小红书 detail 用的就是这个键(复数),之前漏了导致评论数恒为 0
                "comments_count_str",
                "comment_count",
                "comment_count_str",
                "commentCount",
                "commentCountStr",
                "comments",
                "comment_num",
                "commentNum",
                "note_comment_count",
            ],
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
