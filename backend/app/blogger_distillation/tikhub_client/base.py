from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


_http_client: httpx.Client | None = None
_last_request_at: float = 0.0


def _throttle(min_interval: float) -> None:
    """Pace outgoing TikHub requests to at most one per ``min_interval`` seconds.

    Proactively avoids 429s instead of only backing off after hitting one. State is
    a process-wide timestamp; under the worker threadpool it is approximate (a small
    race may let two requests through close together), which is fine for pacing.
    """
    global _last_request_at
    if min_interval <= 0:
        return
    wait = _last_request_at + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


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
    # 列表卡自带的发布时间与浏览量(笔记池 list 级行的数据源;老调用点不传则为空)。
    published_at: datetime | None = None
    view_count: int = 0
    # 列表卡标题(用于采集进度文案「正在采集《标题》」;详情采回后以 normalized 标题为准)。
    title: str = ""


@dataclass
class UserNotesResult:
    """主页笔记候选池 + 是否翻到列表尽头(reached_end=True 才能做下架对账)。"""

    candidates: list[XhsPostCandidate]
    reached_end: bool = False


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
            _throttle(self.settings.tikhub_min_request_interval_seconds)
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
