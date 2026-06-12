from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from typing import Any

from app.blogger_distillation.endpoint_router import DOUYIN_ENDPOINT_POOLS, EndpointRouter, XHS_ENDPOINT_POOLS
from app.blogger_distillation.providers import validate_platform
from app.blogger_distillation.tikhub_client import TikHubBaseClient, first_int, first_str
from app.config import Settings


logger = logging.getLogger(__name__)


@dataclass
class BloggerSearchResult:
    platform: str
    external_id: str
    display_name: str
    homepage_url: str
    avatar_url: str
    description: str
    follower_count: int
    raw: dict[str, Any]


class TikHubUserSearchClient(TikHubBaseClient):
    def __init__(self, settings: Settings, platform: str) -> None:
        super().__init__(settings, missing_key_message="未配置 TIKHUB_API_KEY，无法搜索博主")
        self.platform = validate_platform(platform)
        pools = DOUYIN_ENDPOINT_POOLS if self.platform == "douyin" else XHS_ENDPOINT_POOLS
        self.router = EndpointRouter(self._get, pools)

    def search(self, keyword: str, page: int = 1) -> list[BloggerSearchResult]:
        clean_keyword = keyword.strip()
        if not clean_keyword:
            return []
        try:
            payload = self.router.call(
                "search_users",
                {
                    "keyword": clean_keyword,
                    "page": max(page, 1),
                    "cursor": max(page - 1, 0),
                    "count": 20,
                },
            )
        except RuntimeError as exc:
            if "空数据" in str(exc):
                return []
            raise
        users = adapt_douyin_user_items(payload) if self.platform == "douyin" else extract_user_items(payload)
        results = [result for item in users if (result := normalize_user(self.platform, item))]
        if not results:
            logger.warning(
                "博主搜索没有解析出结果：平台=%s，关键词=%s，endpoint=%s，顶层字段=%s",
                self.platform,
                clean_keyword,
                payload.get("_endpoint_used", "<unknown>"),
                ",".join(payload.keys()),
            )
        return results


def search_bloggers(settings: Settings, platform: str, keyword: str, page: int = 1) -> list[BloggerSearchResult]:
    return TikHubUserSearchClient(settings, platform).search(keyword, page)


def adapt_douyin_user_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    endpoint = str(payload.get("_endpoint_group") or payload.get("_endpoint_used") or "")
    if "search_v2" in endpoint:
        return adapt_douyin_search_v2(payload)
    if "creator" in endpoint:
        return adapt_douyin_creator_search(payload)
    if "search_v1" in endpoint or "fetch_user_search" in endpoint:
        return adapt_douyin_search_v1(payload)
    return extract_user_items(payload)


def adapt_douyin_search_v2(payload: dict[str, Any]) -> list[dict[str, Any]]:
    inner_data = dig(payload, "data", "data", default={})
    user_list = inner_data.get("user_list") if isinstance(inner_data, dict) else []
    users: list[dict[str, Any]] = []
    for item in user_list or []:
        if not isinstance(item, dict):
            continue
        users.append(
            {
                "id": str(item.get("user_id", "")).strip(),
                "nickname": item.get("nick_name", ""),
                "avatar": item.get("avatar_url", ""),
                "fans": normalize_count(item.get("fans_cnt", 0)),
                "description": "",
                "unique_id": "",
                "_raw_platform": "douyin",
                "raw": item,
            }
        )
    return users


def adapt_douyin_search_v1(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = dig(payload, "data", default={})
    user_list = data.get("user_list") if isinstance(data, dict) else []
    users: list[dict[str, Any]] = []
    for item in user_list or []:
        if not isinstance(item, dict):
            continue
        dynamic_patch = item.get("dynamic_patch") or {}
        raw_data = dynamic_patch.get("raw_data") if isinstance(dynamic_patch, dict) else ""
        if not raw_data:
            continue
        try:
            parsed = json.loads(raw_data)
        except (TypeError, ValueError):
            continue
        user_info = parsed.get("user_info") if isinstance(parsed, dict) else {}
        if not isinstance(user_info, dict) or not user_info:
            continue
        avatar_thumb = user_info.get("avatar_thumb") or {}
        url_list = avatar_thumb.get("url_list") if isinstance(avatar_thumb, dict) else []
        users.append(
            {
                "id": user_info.get("sec_uid", ""),
                "nickname": user_info.get("nickname", ""),
                "avatar": url_list[0] if url_list else "",
                "fans": normalize_count(user_info.get("follower_count", 0)),
                "description": user_info.get("signature", ""),
                "unique_id": user_info.get("unique_id", ""),
                "_raw_platform": "douyin",
                "raw": item,
            }
        )
    return users


def adapt_douyin_creator_search(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = dig(payload, "data", default={})
    user_infos = data.get("user_infos") if isinstance(data, dict) else []
    users: list[dict[str, Any]] = []
    for item in user_infos or []:
        if not isinstance(item, dict):
            continue
        users.append(
            {
                "id": str(item.get("user_id", "")).strip(),
                "nickname": item.get("nick_name", ""),
                "avatar": item.get("avatar", ""),
                "fans": normalize_count(item.get("fans", 0)),
                "description": "",
                "unique_id": item.get("short_id", ""),
                "_raw_platform": "douyin",
                "_id_type": "uid",
                "raw": item,
            }
        )
    return users


def extract_user_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[tuple[int, list[dict[str, Any]]]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            normalized = normalize_container_item(node)
            if normalized is not node and looks_like_user(normalized):
                candidates.append((1, [normalized]))
            for key in (
                "users",
                "user_list",
                "userList",
                "user_info_list",
                "userInfoList",
                "user_data",
                "userData",
                "items",
                "item_list",
                "itemList",
                "list",
                "data",
            ):
                value = node.get(key)
                if isinstance(value, list):
                    users = [normalize_container_item(item) for item in value if isinstance(item, dict)]
                    score = sum(1 for item in users if looks_like_user(item))
                    if score:
                        candidates.append((score, users))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            users = [normalize_container_item(item) for item in node if isinstance(item, dict)]
            score = sum(1 for item in users if looks_like_user(item))
            if score:
                candidates.append((score, users))
            for child in node:
                visit(child)

    visit(payload)
    if not candidates:
        return []
    return max(candidates, key=lambda item: item[0])[1]


def normalize_container_item(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("user", "user_info", "userInfo", "author", "author_info", "authorInfo", "card", "user_card", "userCard"):
        value = item.get(key)
        if isinstance(value, dict):
            nested = normalize_container_item(value)
            merged = dict(nested)
            for raw_key, raw_value in item.items():
                if raw_key not in merged and raw_value not in (None, "", [], {}):
                    merged[raw_key] = raw_value
            return merged
    return item


def looks_like_user(item: dict[str, Any]) -> bool:
    return bool(
        deep_first_str(item, ["sec_uid", "secUid", "uid", "user_id", "userId", "userid", "id"])
        and deep_first_str(item, ["nickname", "nick_name", "name", "display_name", "displayName"])
    )


def normalize_user(platform: str, item: dict[str, Any]) -> BloggerSearchResult | None:
    if platform == "douyin":
        external_id = first_str(item, ["id"]) or deep_first_str(item, ["sec_uid", "secUid", "sec_uid_str", "secUidStr", "uid", "user_id", "userId"])
    else:
        external_id = deep_first_str(item, ["user_id", "userId", "userid", "uid", "id"])
    display_name = first_str(item, ["nickname"]) or deep_first_str(item, ["nick_name", "name", "display_name", "displayName"])
    if not external_id or not display_name:
        return None
    homepage_url = deep_first_str(item, ["homepage_url", "share_url", "shareUrl", "url"])
    if not homepage_url:
        homepage_url = build_homepage_url(platform, external_id)
    avatar_url = first_str(item, ["avatar"]) or deep_first_str(
        item,
        ["avatar", "avatar_url", "avatarUrl", "image", "image_url"],
        list_keys=["url_list", "urlList"],
    )
    description = first_str(item, ["description"]) or deep_first_str(item, ["desc", "signature", "user_desc", "userDesc", "signature_extra"])
    follower_count = first_int(item, ["fans"]) or deep_first_int(item, ["follower_count", "fans_count", "fansCount", "followerCount", "followers"])
    return BloggerSearchResult(
        platform=platform,
        external_id=external_id,
        display_name=display_name,
        homepage_url=homepage_url,
        avatar_url=avatar_url,
        description=description,
        follower_count=follower_count,
        raw=item,
    )


def build_homepage_url(platform: str, external_id: str) -> str:
    if platform == "douyin":
        return f"https://www.douyin.com/user/{external_id}"
    return f"https://www.xiaohongshu.com/user/profile/{external_id}"


def dig(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def normalize_count(value: Any) -> str:
    if value is None or value == "":
        return "0"
    if isinstance(value, (int, float)):
        return str(int(value))
    text = str(value).replace(",", "").strip()
    if text.endswith(("w", "W", "万")):
        try:
            return str(int(float(text[:-1]) * 10000))
        except (TypeError, ValueError):
            return "0"
    if text.endswith("亿"):
        try:
            return str(int(float(text[:-1]) * 100_000_000))
        except (TypeError, ValueError):
            return "0"
    try:
        return str(int(text))
    except (TypeError, ValueError):
        return "0"


def deep_first_str(data: Any, keys: list[str], *, list_keys: list[str] | None = None) -> str:
    if isinstance(data, dict):
        direct = first_str(data, keys)
        if direct:
            return direct
        for key in list_keys or []:
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, (str, int)) and str(item).strip():
                        return str(item).strip()
        for value in data.values():
            nested = deep_first_str(value, keys, list_keys=list_keys)
            if nested:
                return nested
    elif isinstance(data, list):
        for item in data:
            nested = deep_first_str(item, keys, list_keys=list_keys)
            if nested:
                return nested
    return ""


def deep_first_int(data: Any, keys: list[str]) -> int:
    if isinstance(data, dict):
        direct = first_int(data, keys)
        if direct:
            return direct
        for value in data.values():
            nested = deep_first_int(value, keys)
            if nested:
                return nested
    elif isinstance(data, list):
        for item in data:
            nested = deep_first_int(item, keys)
            if nested:
                return nested
    return 0
