from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.blogger_distillation.endpoint_router import DOUYIN_ENDPOINT_POOLS, EndpointRouter, XHS_ENDPOINT_POOLS
from app.blogger_distillation.providers import validate_platform
from app.blogger_distillation.tikhub_client import TikHubError, first_int, first_str
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


class TikHubUserSearchClient:
    def __init__(self, settings: Settings, platform: str) -> None:
        if not settings.tikhub_api_key:
            raise TikHubError("未配置 TIKHUB_API_KEY，无法搜索博主")
        self.settings = settings
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
        users = extract_user_items(payload)
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

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.tikhub_base_url.rstrip('/')}{path}"
        method = str(params.pop("_method", "GET")).upper()
        headers = {
            "Authorization": f"Bearer {self.settings.tikhub_api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 PubSync/1.0",
        }
        last_error: TikHubError | None = None
        with httpx.Client(timeout=45) as client:
            for attempt in range(3):
                if attempt:
                    time.sleep(1.2 * attempt)
                clean_params = {key: value for key, value in params.items() if value is not None}
                if method == "POST":
                    response = client.post(url, headers=headers, json=clean_params)
                else:
                    response = client.get(url, headers=headers, params=clean_params)
                try:
                    data = response.json()
                except ValueError as exc:
                    raise TikHubError(f"TikHub 返回非 JSON 响应，HTTP {response.status_code}", response.status_code) from exc
                if response.status_code == 429:
                    last_error = TikHubError(f"TikHub 触发限速，HTTP 429: {data}", 429)
                    continue
                if response.status_code >= 400:
                    raise TikHubError(f"TikHub 请求失败，HTTP {response.status_code}: {data}", response.status_code)
                if not isinstance(data, dict):
                    raise TikHubError("TikHub 返回格式不正确")
                status_code = data.get("code")
                if status_code not in (None, 0, 200):
                    raise TikHubError(f"TikHub 业务错误：{data}")
                return data
        raise last_error or TikHubError("TikHub 请求失败")


def search_bloggers(settings: Settings, platform: str, keyword: str, page: int = 1) -> list[BloggerSearchResult]:
    return TikHubUserSearchClient(settings, platform).search(keyword, page)


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
        external_id = deep_first_str(item, ["sec_uid", "secUid", "sec_uid_str", "secUidStr", "uid", "user_id", "userId", "id"])
    else:
        external_id = deep_first_str(item, ["user_id", "userId", "userid", "uid", "id"])
    display_name = deep_first_str(item, ["nickname", "nick_name", "name", "display_name", "displayName"])
    if not external_id or not display_name:
        return None
    homepage_url = deep_first_str(item, ["homepage_url", "share_url", "shareUrl", "url"])
    if not homepage_url:
        homepage_url = build_homepage_url(platform, external_id)
    avatar_url = deep_first_str(
        item,
        ["avatar", "avatar_url", "avatarUrl", "image", "image_url"],
        list_keys=["url_list", "urlList"],
    )
    description = deep_first_str(item, ["desc", "description", "signature", "user_desc", "userDesc", "signature_extra"])
    follower_count = deep_first_int(item, ["follower_count", "fans_count", "fansCount", "followerCount", "followers", "fans"])
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
