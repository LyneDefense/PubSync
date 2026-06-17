from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.blogger_distillation.endpoint_router import DOUYIN_ENDPOINT_POOLS, EndpointRouter
from app.blogger_distillation.tikhub_client.base import TikHubBaseClient, TikHubError, UserNotesResult, XhsPostCandidate
from app.config import Settings
from app.blogger_distillation.tikhub_client.parsers import (
    extract_douyin_comments,
    extract_douyin_video_page,
    find_cursor,
    first_int,
    first_str,
    normalize_douyin_detail_payload,
    normalize_douyin_user_info,
    normalize_douyin_video_obj,
    parse_douyin_profile_link,
)

logger = logging.getLogger(__name__)


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

    def get_user_notes(
        self,
        homepage_url: str,
        limit: int,
        external_id: str | None = None,
        should_stop: Callable[[list[XhsPostCandidate]], bool] | None = None,
    ) -> UserNotesResult:
        self.user_id = self.user_id or self.resolve_user_id(homepage_url, external_id)
        candidates: list[XhsPostCandidate] = []
        reached_end = False
        seen_ids: set[str] = set()
        cursor = "0"
        for page in range(40):
            payload = self.router.call("user_videos", {"user_id": self.user_id, "cursor": cursor, "count": min(20, max(limit, 1))})
            page_data = extract_douyin_video_page(payload)
            logger.debug(
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
                    return UserNotesResult(candidates=candidates, reached_end=False)
            if should_stop and should_stop(candidates):
                return UserNotesResult(candidates=candidates, reached_end=False)
            next_cursor = page_data["next_cursor"]
            if not page_data["has_more"]:
                reached_end = True
                break
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return UserNotesResult(candidates=candidates[:limit], reached_end=reached_end)

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
