from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings


logger = logging.getLogger(__name__)


class TikHubError(RuntimeError):
    pass


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
    raw: dict[str, Any]


class TikHubXhsClient:
    USER_INFO_PATH = "/api/v1/xiaohongshu/app/v2/get_user_info"
    USER_NOTES_PATH = "/api/v1/xiaohongshu/app/v2/get_user_posted_notes"
    IMAGE_NOTE_DETAIL_PATH = "/api/v1/xiaohongshu/app/v2/get_image_note_detail"
    NOTE_COMMENTS_PATH = "/api/v1/xiaohongshu/app/v2/get_note_comments"

    def __init__(self, settings: Settings) -> None:
        if not settings.tikhub_api_key:
            raise TikHubError("未配置 TIKHUB_API_KEY，无法采集小红书博主内容")
        self.settings = settings
        self.usage = TikHubUsage()

    def get_user_info(self, homepage_url: str) -> dict[str, Any]:
        return self._get(self.USER_INFO_PATH, {"share_text": homepage_url})

    def get_user_notes(self, homepage_url: str, limit: int) -> list[XhsPostCandidate]:
        candidates: list[XhsPostCandidate] = []
        cursor = ""
        seen_ids: set[str] = set()
        for _ in range(10):
            payload = self._get(
                self.USER_NOTES_PATH,
                {"share_text": homepage_url, "cursor": cursor, "num": min(20, max(limit, 1))},
            )
            notes = find_note_candidates(payload)
            for note in notes:
                external_id = first_str(note, ["note_id", "id", "noteId", "note_id_str"])
                if not external_id or external_id in seen_ids:
                    continue
                seen_ids.add(external_id)
                candidates.append(
                    XhsPostCandidate(
                        external_id=external_id,
                        xsec_token=first_str(note, ["xsec_token", "xsecToken", "xsec_source"]) or "",
                        raw=note,
                    )
                )
                if len(candidates) >= limit:
                    return candidates
            next_cursor = find_cursor(payload)
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return candidates[:limit]

    def get_image_note_detail(self, candidate: XhsPostCandidate) -> dict[str, Any]:
        params = {"note_id": candidate.external_id}
        if candidate.xsec_token:
            params["xsec_token"] = candidate.xsec_token
        return self._get(self.IMAGE_NOTE_DETAIL_PATH, params)

    def get_note_comments(self, candidate: XhsPostCandidate, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        comments: list[dict[str, Any]] = []
        cursor = ""
        for _ in range(6):
            params: dict[str, Any] = {
                "note_id": candidate.external_id,
                "cursor": cursor,
                "sort_strategy": "like_count",
                "num": min(20, max(limit, 1)),
            }
            if candidate.xsec_token:
                params["xsec_token"] = candidate.xsec_token
            payload = self._get(self.NOTE_COMMENTS_PATH, params)
            for comment in find_comment_items(payload):
                comments.append(comment)
                if len(comments) >= limit:
                    return comments
            next_cursor = find_cursor(payload)
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return comments[:limit]

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.tikhub_base_url.rstrip('/')}{path}"
        headers = {"Authorization": f"Bearer {self.settings.tikhub_api_key}", "Accept": "application/json"}
        with httpx.Client(timeout=60) as client:
            response = client.get(url, headers=headers, params={key: value for key, value in params.items() if value != ""})
        self.record_request(response)
        try:
            data = response.json()
        except ValueError as exc:
            raise TikHubError(f"TikHub 返回非 JSON 响应，HTTP {response.status_code}") from exc
        if response.status_code >= 400:
            raise TikHubError(f"TikHub 请求失败，HTTP {response.status_code}: {data}")
        if not isinstance(data, dict):
            raise TikHubError("TikHub 返回格式不正确")
        status_code = data.get("code")
        if status_code not in (None, 0, 200):
            raise TikHubError(f"TikHub 业务错误：{data}")
        return data

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
            digits = value.replace(",", "").strip()
            if digits.isdigit():
                return int(digits)
    return 0


def find_note_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lists = find_lists(payload)
    note_lists = [
        items
        for items in lists
        if items
        and isinstance(items[0], dict)
        and any(key in items[0] for key in ("note_id", "noteId", "id", "display_title", "title", "desc"))
    ]
    if not note_lists:
        return []
    return max(note_lists, key=len)


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
