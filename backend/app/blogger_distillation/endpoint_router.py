from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Endpoint:
    group: str
    path: str
    params: dict[str, Any]


XHS_ENDPOINT_POOLS: dict[str, list[Endpoint]] = {
    "user_info": [
        Endpoint("app_v2_share", "/api/v1/xiaohongshu/app_v2/get_user_info", {"share_text": "${share_text}", "xsec_token": "${xsec_token}"}),
        Endpoint("web_v3", "/api/v1/xiaohongshu/web_v3/fetch_user_info", {"user_id": "${user_id}"}),
        Endpoint("app", "/api/v1/xiaohongshu/app/get_user_info", {"user_id": "${user_id}"}),
        Endpoint("app_v2", "/api/v1/xiaohongshu/app_v2/get_user_info", {"user_id": "${user_id}"}),
    ],
    "user_notes": [
        Endpoint(
            "app",
            "/api/v1/xiaohongshu/app/get_user_notes",
            {"user_id": "${user_id}", "cursor": "${cursor}", "num": "${num}", "xsec_token": "${xsec_token}"},
        ),
        Endpoint(
            "app_v2",
            "/api/v1/xiaohongshu/app_v2/get_user_posted_notes",
            {"user_id": "${user_id}", "cursor": "${cursor}", "num": "${num}", "xsec_token": "${xsec_token}"},
        ),
        Endpoint(
            "web_v3",
            "/api/v1/xiaohongshu/web_v3/fetch_user_notes",
            {"user_id": "${user_id}", "cursor": "${cursor}", "num": "${num}", "xsec_token": "${xsec_token}"},
        ),
        Endpoint(
            "app_v2_share",
            "/api/v1/xiaohongshu/app_v2/get_user_posted_notes",
            {"share_text": "${share_text}", "cursor": "${cursor}", "num": "${num}", "xsec_token": "${xsec_token}"},
        ),
    ],
    "image_detail": [
        Endpoint("app", "/api/v1/xiaohongshu/app/get_note_info", {"note_id": "${note_id}"}),
        Endpoint("web_v3", "/api/v1/xiaohongshu/web_v3/fetch_note_detail", {"note_id": "${note_id}", "xsec_token": "${xsec_token}"}),
        Endpoint("app_v2", "/api/v1/xiaohongshu/app_v2/get_image_note_detail", {"note_id": "${note_id}", "xsec_token": "${xsec_token}"}),
        Endpoint("app_v2_no_token", "/api/v1/xiaohongshu/app_v2/get_image_note_detail", {"note_id": "${note_id}"}),
    ],
    "video_detail": [
        Endpoint("app", "/api/v1/xiaohongshu/app/get_note_info", {"note_id": "${note_id}", "xsec_token": "${xsec_token}"}),
        Endpoint("app_no_token", "/api/v1/xiaohongshu/app/get_note_info", {"note_id": "${note_id}"}),
        Endpoint("web_v3", "/api/v1/xiaohongshu/web_v3/fetch_note_detail", {"note_id": "${note_id}", "xsec_token": "${xsec_token}"}),
        Endpoint("app_v2", "/api/v1/xiaohongshu/app_v2/get_video_note_detail", {"note_id": "${note_id}", "xsec_token": "${xsec_token}"}),
        Endpoint("app_v2_no_token", "/api/v1/xiaohongshu/app_v2/get_video_note_detail", {"note_id": "${note_id}"}),
    ],
    "comments": [
        Endpoint("app", "/api/v1/xiaohongshu/app/get_note_comments", {"note_id": "${note_id}", "cursor": "${cursor}", "num": "${num}"}),
        Endpoint("web_v3", "/api/v1/xiaohongshu/web_v3/fetch_note_comments", {"note_id": "${note_id}", "cursor": "${cursor}"}),
        Endpoint(
            "app_v2",
            "/api/v1/xiaohongshu/app_v2/get_note_comments",
            {
                "note_id": "${note_id}",
                "cursor": "${cursor}",
                "index": "${index}",
                "pageArea": "${page_area}",
                "sort_strategy": "like_count",
                "num": "${num}",
                "xsec_token": "${xsec_token}",
            },
        ),
    ],
    "search_users": [
        Endpoint("web_v3", "/api/v1/xiaohongshu/web_v3/fetch_search_users", {"keyword": "${keyword}", "page": "${page}"}),
        Endpoint("app", "/api/v1/xiaohongshu/app/search_users", {"keyword": "${keyword}", "page": "${page}"}),
        Endpoint("app_v2", "/api/v1/xiaohongshu/app_v2/search_users", {"keyword": "${keyword}", "page": "${page}"}),
    ],
}


DOUYIN_ENDPOINT_POOLS: dict[str, list[Endpoint]] = {
    "search_users": [
        Endpoint(
            "search_v2",
            "/api/v1/douyin/search/fetch_user_search_v2",
            {"_method": "POST", "keyword": "${keyword}", "cursor": "${cursor}"},
        ),
        Endpoint(
            "search_v1",
            "/api/v1/douyin/search/fetch_user_search",
            {
                "_method": "POST",
                "keyword": "${keyword}",
                "cursor": "${cursor}",
                "douyin_user_fans": "",
                "douyin_user_type": "",
                "search_id": "",
            },
        ),
        Endpoint("creator", "/api/v1/douyin/creator/fetch_user_search", {"user_name": "${keyword}", "cursor": "${cursor}", "count": "${count}"}),
    ],
    "user_info": [
        Endpoint("app", "/api/v1/douyin/app/v3/handler_user_profile", {"sec_user_id": "${user_id}"}),
        Endpoint("web", "/api/v1/douyin/web/handler_user_profile", {"sec_user_id": "${user_id}"}),
    ],
    "user_videos": [
        Endpoint("app", "/api/v1/douyin/app/v3/fetch_user_post_videos", {"sec_user_id": "${user_id}", "max_cursor": "${cursor}", "count": "${count}"}),
        Endpoint("web", "/api/v1/douyin/web/fetch_user_post_videos", {"sec_uid": "${user_id}", "max_cursor": "${cursor}", "count": "${count}"}),
        Endpoint("app_v2", "/api/v1/douyin/app/v2/fetch_user_post", {"sec_user_id": "${user_id}", "max_cursor": "${cursor}"}),
    ],
    "video_detail": [
        Endpoint("app", "/api/v1/douyin/app/v3/fetch_one_video", {"aweme_id": "${video_id}"}),
        Endpoint("web", "/api/v1/douyin/web/fetch_video_detail", {"aweme_id": "${video_id}"}),
    ],
    "comments": [
        Endpoint("app", "/api/v1/douyin/app/v3/fetch_video_comments", {"aweme_id": "${video_id}", "cursor": "${cursor}", "count": "${count}"}),
        Endpoint("web", "/api/v1/douyin/web/fetch_video_comments", {"aweme_id": "${video_id}", "cursor": "${cursor}", "count": "${count}"}),
    ],
}


class EndpointRouter:
    degradable_status_codes = {400, 404, 422, 500, 502, 503, 504}
    blocking_status_codes = {401, 402, 403}

    def __init__(self, request_func: Callable[[str, dict[str, Any]], dict[str, Any]], pools: dict[str, list[Endpoint]] | None = None) -> None:
        self.request_func = request_func
        self.pools = pools or XHS_ENDPOINT_POOLS
        self.dead_endpoints: set[str] = set()
        self.empty_counts: dict[str, int] = {}

    def call(self, pool_name: str, args: dict[str, Any], *, allow_empty: bool = False) -> dict[str, Any]:
        endpoints = self.pools.get(pool_name)
        if not endpoints:
            raise RuntimeError(f"未知 TikHub endpoint 池：{pool_name}")

        errors: list[str] = []
        for endpoint in endpoints:
            endpoint_key = f"{endpoint.group}:{endpoint.path}"
            if endpoint_key in self.dead_endpoints:
                continue
            params = self._render_params(endpoint.params, args)
            try:
                payload = self.request_func(endpoint.path, params)
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                errors.append(f"{endpoint_key} -> {type(exc).__name__}: {exc}")
                if status_code in self.blocking_status_codes:
                    raise
                if status_code in self.degradable_status_codes or status_code is None:
                    self.dead_endpoints.add(endpoint_key)
                    logger.warning("TikHub endpoint 降级：池=%s，端点=%s，原因=%s", pool_name, endpoint_key, exc)
                    continue
                raise

            if allow_empty or not is_empty_payload(payload):
                payload["_endpoint_used"] = endpoint_key
                payload["_endpoint_group"] = endpoint.group
                return payload

            self.empty_counts[endpoint_key] = self.empty_counts.get(endpoint_key, 0) + 1
            if self.empty_counts[endpoint_key] >= 2:
                self.dead_endpoints.add(endpoint_key)
            errors.append(f"{endpoint_key} -> 空数据")
            logger.warning("TikHub endpoint 返回空数据：池=%s，端点=%s", pool_name, endpoint_key)

        raise RuntimeError(f"TikHub endpoint 池全部失败：{pool_name}；{'；'.join(errors[-5:])}")

    @staticmethod
    def _render_params(template: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                arg_name = value[2:-1]
                arg_value = args.get(arg_name)
                if arg_value not in (None, ""):
                    params[key] = arg_value
            elif value not in (None, ""):
                params[key] = value
        return params


def is_empty_payload(value: Any) -> bool:
    if value in (None, "", []):
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        if any(key in value for key in ("note_id", "noteId", "id", "title", "desc", "content", "user_id", "userId")):
            return False
        if recursive_find_any(value, ("note_id", "noteId", "id", "title", "desc", "content", "user_id", "userId", "nickname")):
            return False
        lists = find_lists(value)
        if any(items for items in lists):
            return False
        inner_values = [item for item in value.values() if item not in (None, "", [], {})]
        return len(inner_values) == 0
    return False


def recursive_find_any(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            if value.get(key) not in (None, "", [], {}):
                return value[key]
        for child in value.values():
            found = recursive_find_any(child, keys)
            if found not in (None, "", [], {}):
                return found
    elif isinstance(value, list):
        for child in value:
            found = recursive_find_any(child, keys)
            if found not in (None, "", [], {}):
                return found
    return None


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
