from __future__ import annotations

import logging
from typing import Any

from app.blogger_distillation.endpoint_router import EndpointRouter
from app.blogger_distillation.tikhub_client.base import TikHubBaseClient, TikHubError, UserNotesResult, XhsPostCandidate
from app.config import Settings
from app.blogger_distillation.tikhub_client.parsers import (
    detect_note_type,
    extract_interaction_counts,
    extract_note_page,
    extract_xsec_token,
    find_comment_items,
    find_cursor,
    find_index,
    find_page_area,
    find_user_id,
    first_str,
    parse_xhs_profile_link,
    score_note_page,
)

logger = logging.getLogger(__name__)


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

    def get_user_notes(self, homepage_url: str, limit: int, external_id: str | None = None) -> UserNotesResult:
        link = parse_xhs_profile_link(homepage_url)
        self.user_id = self.user_id or (external_id or "").strip() or link["user_id"]
        self.profile_xsec_token = self.profile_xsec_token or link["xsec_token"]
        candidates: list[XhsPostCandidate] = []
        reached_end = False
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
            logger.debug(
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
                    return UserNotesResult(candidates=candidates, reached_end=False)
            next_cursor = page_data["next_cursor"]
            # 兜底:has_more 为真但没解析到游标时,用最后一条 note_id 当游标(小红书常见做法),
            # 否则会卡在第 1 页(~20 条)永远翻不动。重复/同游标会在下面 break,不会死循环。
            if page_data["has_more"] and not next_cursor and candidates:
                next_cursor = candidates[-1].external_id
            logger.info(
                "小红书翻页:page=%s,本页=%s,累计候选=%s,has_more=%s,next_cursor=%s",
                page + 1,
                len(notes),
                len(candidates),
                page_data["has_more"],
                next_cursor or "<empty>",
            )
            if not page_data["has_more"]:
                reached_end = True
                break
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return UserNotesResult(candidates=candidates[:limit], reached_end=reached_end)

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
                logger.debug(
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
            logger.debug(
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
                logger.debug(
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
