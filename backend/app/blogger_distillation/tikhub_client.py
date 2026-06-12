from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import Settings
from app.blogger_distillation.endpoint_router import DOUYIN_ENDPOINT_POOLS, EndpointRouter


logger = logging.getLogger(__name__)


_http_client: httpx.Client | None = None


def shared_http_client() -> httpx.Client:
    """Process-wide pooled httpx client.

    The TikHub clients issue many sequential requests per collection run; opening a
    fresh ``httpx.Client`` per request (the previous behaviour) threw away connection
    pooling and TLS session reuse. A single shared client is thread-safe for sending
    requests, so it is safe to reuse across the background-task threadpool. Per-request
    timeouts are still passed at call sites that need a non-default value.
    """
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(
            timeout=60,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http_client


class TikHubError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class TikHubUsage:
    request_count: int = 0
    estimated_cost_usd: float = 0
    cost_min_usd: float = 0
    cost_max_usd: float = 0


@dataclass
class XhsPostCandidate:
    external_id: str
    xsec_token: str
    note_type: str
    like_count: int
    favorite_count: int
    comment_count: int
    share_count: int
    raw: dict[str, Any]


def summarize_payload(data: Any, limit: int = 300) -> str:
    """Render a TikHub response for an error message, truncated to avoid dumping
    huge (and potentially sensitive) payloads into logs and task events."""
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
    return text if len(text) <= limit else f"{text[:limit]}…(已截断)"


class TikHubBaseClient:
    """Shared HTTP layer for the TikHub clients.

    Owns the Bearer-authenticated request loop — retries, rate-limit (429)
    handling, JSON/business-error checks and usage accounting — so the XHS,
    Douyin and user-search clients differ only in their endpoint pools and
    response parsing, not in transport. A single pooled httpx client is reused
    across all requests (see ``shared_http_client``).
    """

    def __init__(self, settings: Settings, *, missing_key_message: str) -> None:
        if not settings.tikhub_api_key:
            raise TikHubError(missing_key_message)
        self.settings = settings
        self.usage = TikHubUsage()

    def _get(self, path: str, params: dict[str, Any], *, timeout: float = 60) -> dict[str, Any]:
        url = f"{self.settings.tikhub_base_url.rstrip('/')}{path}"
        method = str(params.pop("_method", "GET")).upper()
        headers = {
            "Authorization": f"Bearer {self.settings.tikhub_api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 PubSync/1.0",
        }
        clean_params = {key: value for key, value in params.items() if value not in (None, "")}
        client = shared_http_client()
        last_error: TikHubError | None = None
        for attempt in range(3):
            if attempt:
                time.sleep(1.5 * attempt)
            if method == "POST":
                response = client.post(url, headers=headers, json=clean_params, timeout=timeout)
            else:
                response = client.get(url, headers=headers, params=clean_params, timeout=timeout)
            self.record_request(response)
            try:
                data = response.json()
            except ValueError as exc:
                raise TikHubError(f"TikHub 返回非 JSON 响应，HTTP {response.status_code}", response.status_code) from exc
            if response.status_code == 429:
                last_error = TikHubError("TikHub 触发限速，HTTP 429", 429)
                continue
            if response.status_code >= 400:
                raise TikHubError(
                    f"TikHub 请求失败，HTTP {response.status_code}：{summarize_payload(data)}", response.status_code
                )
            if not isinstance(data, dict):
                raise TikHubError("TikHub 返回格式不正确")
            status_code = data.get("code")
            if status_code not in (None, 0, 200):
                raise TikHubError(f"TikHub 业务错误：{summarize_payload(data)}")
            return data
        raise last_error or TikHubError("TikHub 请求失败")

    def record_request(self, response: httpx.Response) -> None:
        self.usage.request_count += 1
        self.usage.estimated_cost_usd += self.settings.tikhub_request_price_usd
        self.usage.cost_min_usd += self.settings.tikhub_min_request_price_usd
        self.usage.cost_max_usd += self.settings.tikhub_max_request_price_usd
        cost_header = response.headers.get("x-tikhub-cost-usd") or response.headers.get("x-cost-usd")
        if cost_header:
            try:
                self.usage.estimated_cost_usd = float(cost_header)
            except ValueError:
                logger.debug("TikHub 费用响应头无法解析：%s", cost_header)


class TikHubXhsClient(TikHubBaseClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, missing_key_message="未配置 TIKHUB_API_KEY，无法采集小红书博主内容")
        self.router = EndpointRouter(self._get)
        self.user_id = ""
        self.profile_xsec_token = ""

    def get_user_info(self, homepage_url: str, external_id: str | None = None) -> dict[str, Any]:
        link = parse_xhs_profile_link(homepage_url)
        self.user_id = self.user_id or (external_id or "").strip() or link["user_id"]
        self.profile_xsec_token = self.profile_xsec_token or link["xsec_token"]
        payload = self.router.call(
            "user_info",
            {"share_text": link["share_text"], "user_id": self.user_id, "xsec_token": self.profile_xsec_token},
        )
        self.user_id = self.user_id or find_user_id(payload)
        return payload

    def get_user_notes(self, homepage_url: str, limit: int, external_id: str | None = None) -> list[XhsPostCandidate]:
        link = parse_xhs_profile_link(homepage_url)
        self.user_id = self.user_id or (external_id or "").strip() or link["user_id"]
        self.profile_xsec_token = self.profile_xsec_token or link["xsec_token"]
        candidates: list[XhsPostCandidate] = []
        cursor = ""
        seen_ids: set[str] = set()
        for page in range(20):
            try:
                page_data = self.fetch_user_notes_page(link, cursor, min(20, max(limit, 1)))
            except TikHubError:
                if candidates:
                    logger.warning(
                        "小红书主页笔记分页中断，保留已获取候选：page=%s，cursor=%s，已获取=%s",
                        page + 1,
                        cursor or "<empty>",
                        len(candidates),
                    )
                    break
                raise
            notes = page_data["notes"]
            logger.info(
                "小红书主页笔记分页：page=%s，cursor=%s，解析=%s，has_more=%s，next_cursor=%s",
                page + 1,
                cursor or "<empty>",
                len(notes),
                page_data["has_more"],
                page_data["next_cursor"] or "<empty>",
            )
            for note in notes:
                external_id = first_str(note, ["note_id", "id", "noteId", "note_id_str"])
                if not external_id or external_id in seen_ids:
                    continue
                seen_ids.add(external_id)
                counts = extract_interaction_counts(note)
                candidates.append(
                    XhsPostCandidate(
                        external_id=external_id,
                        xsec_token=extract_xsec_token(note) or self.profile_xsec_token,
                        note_type=detect_note_type(note),
                        like_count=counts["like_count"],
                        favorite_count=counts["favorite_count"],
                        comment_count=counts["comment_count"],
                        share_count=counts["share_count"],
                        raw=note,
                    )
                )
                if len(candidates) >= limit:
                    return candidates
            next_cursor = page_data["next_cursor"]
            if not page_data["has_more"] and not next_cursor:
                break
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return candidates[:limit]

    def fetch_user_notes_page(self, link: dict[str, str], cursor: str, num: int) -> dict[str, Any]:
        errors: list[str] = []
        best_page: dict[str, Any] | None = None
        best_endpoint = ""
        best_score = -1
        args = {
            "share_text": link["share_text"],
            "user_id": self.user_id,
            "xsec_token": self.profile_xsec_token,
            "cursor": cursor,
            "num": num,
        }
        for endpoint in self.router.pools.get("user_notes", []):
            params = EndpointRouter._render_params(endpoint.params, args)
            try:
                payload = self._get(endpoint.path, params)
            except Exception as exc:
                errors.append(f"{endpoint.group}: {exc}")
                logger.warning("TikHub 用户笔记端点失败：端点=%s:%s，错误=%s", endpoint.group, endpoint.path, exc)
                continue
            page_data = extract_note_page(payload)
            if page_data["notes"]:
                payload["_endpoint_used"] = f"{endpoint.group}:{endpoint.path}"
                score = score_note_page(page_data, num)
                logger.info(
                    "TikHub 用户笔记端点候选：端点=%s，解析=%s，has_more=%s，next_cursor=%s，评分=%s",
                    payload["_endpoint_used"],
                    len(page_data["notes"]),
                    page_data["has_more"],
                    page_data["next_cursor"] or "<empty>",
                    score,
                )
                if score > best_score:
                    best_page = page_data
                    best_endpoint = payload["_endpoint_used"]
                    best_score = score
                continue
            logger.warning("TikHub 用户笔记端点返回空：端点=%s:%s", endpoint.group, endpoint.path)
        if best_page is not None:
            logger.info(
                "TikHub 用户笔记端点选用：端点=%s，解析=%s，has_more=%s，next_cursor=%s",
                best_endpoint,
                len(best_page["notes"]),
                best_page["has_more"],
                best_page["next_cursor"] or "<empty>",
            )
            return best_page
        raise TikHubError(f"TikHub 用户笔记列表为空或全部失败：{'；'.join(errors[-5:])}")

    def get_image_note_detail(self, candidate: XhsPostCandidate) -> dict[str, Any]:
        pool = "video_detail" if candidate.note_type == "video" else "image_detail"
        return self.router.call(pool, {"note_id": candidate.external_id, "xsec_token": candidate.xsec_token})

    def get_video_note_detail_variants(self, candidate: XhsPostCandidate) -> list[dict[str, Any]]:
        variants: list[dict[str, Any]] = []
        for endpoint in self.router.pools.get("video_detail", []):
            if endpoint.group == "web_v3" and not candidate.xsec_token:
                logger.info(
                    "跳过需要 xsec_token 的视频详情端点：端点=%s:%s，note_id=%s",
                    endpoint.group,
                    endpoint.path,
                    candidate.external_id,
                )
                continue
            params = EndpointRouter._render_params(
                endpoint.params,
                {"note_id": candidate.external_id, "xsec_token": candidate.xsec_token},
            )
            try:
                payload = self._get(endpoint.path, params)
            except Exception as exc:
                logger.warning("TikHub 视频详情补取失败：端点=%s:%s，note_id=%s，错误=%s", endpoint.group, endpoint.path, candidate.external_id, exc)
                continue
            payload["_endpoint_used"] = f"{endpoint.group}:{endpoint.path}"
            payload["_endpoint_group"] = endpoint.group
            variants.append(payload)
        return variants

    def get_note_comments(self, candidate: XhsPostCandidate, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        comments: list[dict[str, Any]] = []
        cursor = ""
        index = 0
        page_area = "UNFOLDED"
        for _ in range(6):
            params: dict[str, Any] = {
                "note_id": candidate.external_id,
                "cursor": cursor,
                "index": index,
                "pageArea": page_area,
                "sort_strategy": "like_count",
                "num": min(20, max(limit, 1)),
            }
            if candidate.xsec_token:
                params["xsec_token"] = candidate.xsec_token
            payload = self.router.call("comments", params, allow_empty=True)
            for comment in find_comment_items(payload):
                comments.append(comment)
                if len(comments) >= limit:
                    return comments
            next_cursor = find_cursor(payload)
            index = find_index(payload) or len(comments)
            page_area = find_page_area(payload) or page_area
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return comments[:limit]


class TikHubDouyinClient(TikHubBaseClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, missing_key_message="未配置 TIKHUB_API_KEY，无法采集抖音博主内容")
        self.router = EndpointRouter(self._get, DOUYIN_ENDPOINT_POOLS)
        self.user_id = ""

    def get_user_info(self, homepage_url: str, external_id: str | None = None) -> dict[str, Any]:
        self.user_id = self.resolve_user_id(homepage_url, external_id)
        payload = self.router.call("user_info", {"user_id": self.user_id})
        info = normalize_douyin_user_info(payload)
        if info.get("id"):
            self.user_id = info["id"]
        return payload

    def get_user_notes(self, homepage_url: str, limit: int, external_id: str | None = None) -> list[XhsPostCandidate]:
        self.user_id = self.user_id or self.resolve_user_id(homepage_url, external_id)
        candidates: list[XhsPostCandidate] = []
        seen_ids: set[str] = set()
        cursor = "0"
        for page in range(10):
            payload = self.router.call("user_videos", {"user_id": self.user_id, "cursor": cursor, "count": min(20, max(limit, 1))})
            page_data = extract_douyin_video_page(payload)
            logger.info(
                "抖音主页作品分页：page=%s，cursor=%s，解析=%s，has_more=%s，next_cursor=%s",
                page + 1,
                cursor,
                len(page_data["items"]),
                page_data["has_more"],
                page_data["next_cursor"] or "<empty>",
            )
            for item in page_data["items"]:
                external_id = first_str(item, ["id"])
                if not external_id or external_id in seen_ids:
                    continue
                seen_ids.add(external_id)
                candidates.append(
                    XhsPostCandidate(
                        external_id=external_id,
                        xsec_token="",
                        note_type="video",
                        like_count=first_int(item, ["likes"]),
                        favorite_count=first_int(item, ["collects"]),
                        comment_count=first_int(item, ["comments"]),
                        share_count=first_int(item, ["shares"]),
                        raw=normalize_douyin_video_obj(item),
                    )
                )
                if len(candidates) >= limit:
                    return candidates
            next_cursor = page_data["next_cursor"]
            if not page_data["has_more"] or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return candidates[:limit]

    def get_image_note_detail(self, candidate: XhsPostCandidate) -> dict[str, Any]:
        payload = self.router.call("video_detail", {"video_id": candidate.external_id})
        return normalize_douyin_detail_payload(payload, candidate)

    def get_video_note_detail_variants(self, candidate: XhsPostCandidate) -> list[dict[str, Any]]:
        variants: list[dict[str, Any]] = []
        for endpoint in self.router.pools.get("video_detail", []):
            params = EndpointRouter._render_params(endpoint.params, {"video_id": candidate.external_id})
            try:
                payload = self._get(endpoint.path, params)
            except Exception as exc:
                logger.warning("TikHub 抖音视频详情补取失败：端点=%s:%s，video_id=%s，错误=%s", endpoint.group, endpoint.path, candidate.external_id, exc)
                continue
            payload["_endpoint_used"] = f"{endpoint.group}:{endpoint.path}"
            payload["_endpoint_group"] = endpoint.group
            variants.append(normalize_douyin_detail_payload(payload, candidate))
        return variants

    def get_note_comments(self, candidate: XhsPostCandidate, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        comments: list[dict[str, Any]] = []
        cursor = "0"
        for _ in range(6):
            payload = self.router.call(
                "comments",
                {"video_id": candidate.external_id, "cursor": cursor, "count": min(20, max(limit, 1))},
                allow_empty=True,
            )
            comments.extend(extract_douyin_comments(payload))
            if len(comments) >= limit:
                return comments[:limit]
            next_cursor = find_cursor(payload)
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return comments[:limit]

    def resolve_user_id(self, homepage_url: str, external_id: str | None) -> str:
        user_id = (external_id or "").strip() or parse_douyin_profile_link(homepage_url)
        if not user_id:
            raise TikHubError("请输入抖音博主主页链接，格式应为 https://www.douyin.com/user/{sec_uid}")
        if user_id.isdigit():
            payload = self._get("/api/v1/douyin/web/fetch_user_profile_by_uid", {"uid": user_id})
            info = normalize_douyin_user_info(payload)
            user_id = info.get("id") or user_id
        return user_id


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
