from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import Settings
from app.blogger_distillation.endpoint_router import EndpointRouter


logger = logging.getLogger(__name__)


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


class TikHubXhsClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.tikhub_api_key:
            raise TikHubError("未配置 TIKHUB_API_KEY，无法采集小红书博主内容")
        self.settings = settings
        self.usage = TikHubUsage()
        self.router = EndpointRouter(self._get)
        self.user_id = ""
        self.profile_xsec_token = ""

    def get_user_info(self, homepage_url: str) -> dict[str, Any]:
        link = parse_xhs_profile_link(homepage_url)
        self.user_id = self.user_id or link["user_id"]
        self.profile_xsec_token = self.profile_xsec_token or link["xsec_token"]
        payload = self.router.call(
            "user_info",
            {"share_text": link["share_text"], "user_id": self.user_id, "xsec_token": self.profile_xsec_token},
        )
        self.user_id = self.user_id or find_user_id(payload)
        return payload

    def get_user_notes(self, homepage_url: str, limit: int) -> list[XhsPostCandidate]:
        link = parse_xhs_profile_link(homepage_url)
        self.user_id = self.user_id or link["user_id"]
        self.profile_xsec_token = self.profile_xsec_token or link["xsec_token"]
        candidates: list[XhsPostCandidate] = []
        cursor = ""
        seen_ids: set[str] = set()
        for page in range(20):
            page_data = self.fetch_user_notes_page(link, cursor, min(20, max(limit, 1)))
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
                logger.info("TikHub 用户笔记端点命中：端点=%s，解析=%s", payload["_endpoint_used"], len(page_data["notes"]))
                return page_data
            logger.warning("TikHub 用户笔记端点返回空：端点=%s:%s", endpoint.group, endpoint.path)
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

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.tikhub_base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.settings.tikhub_api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 PubSync/1.0",
        }
        last_error: TikHubError | None = None
        with httpx.Client(timeout=60) as client:
            for attempt in range(3):
                if attempt:
                    time.sleep(1.5 * attempt)
                response = client.get(url, headers=headers, params={key: value for key, value in params.items() if value != ""})
                self.record_request(response)
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


def extract_note_page(payload: dict[str, Any]) -> dict[str, Any]:
    page = find_best_note_container(payload)
    if page is None:
        return {"notes": [], "next_cursor": "", "has_more": False}
    notes = [normalize_feed_item(item) for item in extract_container_items(page)]
    notes = [item for item in notes if first_str(item, ["note_id", "id", "noteId", "display_title", "title"])]
    return {
        "notes": notes,
        "next_cursor": find_container_cursor(page, notes),
        "has_more": first_bool(page, ["has_more", "hasMore", "has_more_note"]),
    }


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


def find_container_cursor(container: dict[str, Any], notes: list[dict[str, Any]]) -> str:
    for key in ("next_cursor", "nextCursor", "cursor", "lastCursor", "last_cursor"):
        value = container.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    for note in reversed(notes):
        value = note.get("cursor")
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return ""


def extract_interaction_counts(value: dict[str, Any]) -> dict[str, int]:
    interact = recursive_find(value, "interact_info") or recursive_find(value, "interactInfo")
    sources = [item for item in (interact, value) if isinstance(item, dict)]
    return {
        "like_count": first_count(sources, ["liked_count", "liked_count_str", "likedCount", "like_count", "likeCount", "likes"]),
        "favorite_count": first_count(
            sources,
            ["collected_count", "collected_count_str", "collectedCount", "favorite_count", "collect_count", "collects"],
        ),
        "comment_count": first_count(sources, ["comment_count", "comment_count_str", "commentCount", "comments"]),
        "share_count": first_count(sources, ["share_count", "share_count_str", "shareCount", "sharedCount", "shares"]),
    }


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
    for key in ("cursor", "next_cursor", "nextCursor", "last_cursor"):
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
