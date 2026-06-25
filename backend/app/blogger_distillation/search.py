from __future__ import annotations

import logging
import json
import re
from dataclasses import dataclass
from typing import Any

from app.blogger_distillation.endpoint_router import DOUYIN_ENDPOINT_POOLS, EndpointRouter, XHS_ENDPOINT_POOLS
from app.blogger_distillation.providers import validate_platform
from app.blogger_distillation.tikhub_client import TikHubBaseClient, first_int, first_str
from app.config import Settings


logger = logging.getLogger(__name__)


# 粉丝数合理上限:全网最大号也就 ~1 亿,超过基本是把"小红书号/用户ID"当成了粉丝数。
MAX_PLAUSIBLE_FOLLOWERS = 200_000_000


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
    follower_known: bool = True  # 解析不到/明显是ID → False,前端显示「粉丝未知」而非乱码数字


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


class TikHubNoteSearchClient(TikHubBaseClient):
    """搜笔记 → 取作者(泛搜索 B 路)。只小红书;失败/取不到一律返回空,由上层退化到 A 路。"""

    def __init__(self, settings: Settings, platform: str) -> None:
        super().__init__(settings, missing_key_message="未配置 TIKHUB_API_KEY，无法搜索笔记")
        self.platform = validate_platform(platform)
        pools = DOUYIN_ENDPOINT_POOLS if self.platform == "douyin" else XHS_ENDPOINT_POOLS
        self.router = EndpointRouter(self._get, pools)

    def search_authors(self, keyword: str, page: int = 1) -> list[BloggerSearchResult]:
        clean = keyword.strip()
        if not clean or "search_notes" not in (DOUYIN_ENDPOINT_POOLS if self.platform == "douyin" else XHS_ENDPOINT_POOLS):
            return []
        try:
            payload = self.router.call("search_notes", {"keyword": clean, "page": max(page, 1), "cursor": max(page - 1, 0)})
        except RuntimeError as exc:
            if "空数据" in str(exc):
                logger.warning("笔记搜索:全部端点返回空数据 关键词=%s", clean)
                return []
            raise
        # 漏斗式日志:端点 → 笔记数 → 去重作者数。区分「端点没返回」「返回了但解析不出笔记」「有笔记但取不到作者」。
        endpoint = payload.get("_endpoint_used", "?")
        notes = _extract_note_items(payload)
        authors = _authors_from_notes(self.platform, payload)
        if not notes:
            logger.warning(
                "笔记搜索:端点返回了数据但没解析出笔记列表 关键词=%s 端点=%s 顶层字段=%s",
                clean, endpoint, ",".join(list(payload.keys())[:12]),
            )
        elif not authors:
            logger.warning("笔记搜索:解析出 %d 条笔记但没取到作者 关键词=%s 端点=%s", len(notes), clean, endpoint)
        else:
            logger.info("笔记搜索取作者 关键词=%s 端点=%s 笔记=%d → 去重作者=%d", clean, endpoint, len(notes), len(authors))
        return authors


def _extract_note_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从笔记搜索响应里尽力取出笔记列表(跨端点字段不一,best-effort)。"""
    for path in (("data", "items"), ("data", "notes"), ("data", "data", "items"), ("data", "data", "notes"), ("items",), ("notes",)):
        node = dig(payload, *path, default=None)
        if isinstance(node, list) and node:
            return [x for x in node if isinstance(x, dict)]
    node = dig(payload, "data", default=None)
    return [x for x in node if isinstance(x, dict)] if isinstance(node, list) else []


def _authors_from_notes(platform: str, payload: dict[str, Any]) -> list[BloggerSearchResult]:
    """笔记列表 → 去重取作者。取不到作者的笔记跳过。"""
    out: list[BloggerSearchResult] = []
    seen: set[str] = set()
    for note in _extract_note_items(payload):
        author = None
        # 作者可能直接挂在 note 上,或挂在 note_card / noteCard(web_v3 搜索是 camelCase)下。
        for key in ("user", "author"):
            if isinstance(note.get(key), dict):
                author = note[key]
                break
        if author is None:
            for card_key in ("note_card", "noteCard", "card"):
                card = note.get(card_key)
                if isinstance(card, dict):
                    for key in ("user", "author"):
                        if isinstance(card.get(key), dict):
                            author = card[key]
                            break
                if author is not None:
                    break
        if not isinstance(author, dict):
            continue
        result = normalize_user(platform, author)
        if result and result.external_id not in seen:
            seen.add(result.external_id)
            out.append(result)
    return out


def search_note_authors(settings: Settings, platform: str, keyword: str, page: int = 1) -> list[BloggerSearchResult]:
    """泛搜索 B 路:搜该关键词的笔记,取作者。任何异常 → 空(不阻断召回)。"""
    try:
        return TikHubNoteSearchClient(settings, platform).search_authors(keyword, page)
    except Exception as exc:  # noqa: BLE001 - B 路失败退化到 A 路
        logger.warning("笔记搜索取作者失败(降级):平台=%s,关键词=%s,%s", platform, keyword, exc)
        return []


class TikHubFollowingClient(TikHubBaseClient):
    """拉用户关注列表(泛搜索 C 路:种子→同类号)。取不到一律返回空,由上层退化。"""

    def __init__(self, settings: Settings, platform: str) -> None:
        super().__init__(settings, missing_key_message="未配置 TIKHUB_API_KEY，无法拉关注列表")
        self.platform = validate_platform(platform)
        pools = DOUYIN_ENDPOINT_POOLS if self.platform == "douyin" else XHS_ENDPOINT_POOLS
        self.router = EndpointRouter(self._get, pools)

    def following(self, user_id: str, xsec_token: str = "", limit: int = 60) -> list[BloggerSearchResult]:
        uid = (user_id or "").strip()
        pools = DOUYIN_ENDPOINT_POOLS if self.platform == "douyin" else XHS_ENDPOINT_POOLS
        if not uid or "user_following" not in pools:
            return []
        try:
            payload = self.router.call(
                "user_following", {"user_id": uid, "cursor": 0, "num": max(limit, 20), "xsec_token": xsec_token}
            )
        except RuntimeError as exc:
            if "空数据" in str(exc):
                logger.warning("关注列表:全部端点返回空数据 user_id=%s", uid)
                return []
            raise
        endpoint = payload.get("_endpoint_used", "?")
        items = extract_user_items(payload)
        results = [r for item in items if (r := normalize_user(self.platform, item))]
        if not results:
            logger.warning("关注列表:端点返回了数据但没解析出用户 user_id=%s 端点=%s 顶层字段=%s",
                           uid, endpoint, ",".join(list(payload.keys())[:12]))
        else:
            logger.info("关注列表 user_id=%s 端点=%s → 用户=%d", uid, endpoint, len(results))
        return results[:limit]


def get_user_following(settings: Settings, platform: str, user_id: str, xsec_token: str = "", limit: int = 60) -> list[BloggerSearchResult]:
    """泛搜索 C 路:拉某个种子账号的关注列表。任何异常 → 空(不阻断召回)。"""
    try:
        return TikHubFollowingClient(settings, platform).following(user_id, xsec_token, limit)
    except Exception as exc:  # noqa: BLE001 - C 路失败不阻断
        logger.warning("拉关注列表失败(降级):平台=%s,user_id=%s,%s", platform, user_id, exc)
        return []


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


# 搜索结果里混着的"筛选项/聚合块"标志键(如粉丝区间筛选 All/0-100/100-1k),据此排除。
FILTER_MARKER_KEYS = ("sub_filters", "sub_filters_select_type", "need_location_info", "icon_tail_url")
# 真实用户至少带一个这样的信号(头像/链接/小红书号/粉丝文案/简介)。
USER_SIGNAL_KEYS = [
    "avatar", "avatar_url", "avatarUrl", "image", "image_url", "imageUrl",
    "red_id", "redId", "sub_title", "subTitle", "link", "share_url", "shareUrl",
    "homepage_url", "signature", "desc", "follower_count", "fans_count",
]


def looks_like_user(item: dict[str, Any]) -> bool:
    has_id = deep_first_str(item, ["sec_uid", "secUid", "uid", "user_id", "userId", "userid", "id"])
    has_name = deep_first_str(item, ["nickname", "nick_name", "name", "display_name", "displayName"])
    if not (has_id and has_name):
        return False
    # 排除粉丝区间筛选项等噪声块。
    if any(key in item for key in FILTER_MARKER_KEYS):
        return False
    # 必须带至少一个用户信号,避免把纯 id+name 的非用户对象当成博主。
    return bool(deep_first_str(item, USER_SIGNAL_KEYS) or deep_first_int(item, ["follower_count", "fans_count", "fansCount"]))


def normalize_user(platform: str, item: dict[str, Any]) -> BloggerSearchResult | None:
    if platform == "douyin":
        external_id = first_str(item, ["id"]) or deep_first_str(item, ["sec_uid", "secUid", "sec_uid_str", "secUidStr", "uid", "user_id", "userId"])
    else:
        external_id = deep_first_str(item, ["user_id", "userId", "userid", "uid", "id"])
    display_name = first_str(item, ["nickname"]) or deep_first_str(item, ["nick_name", "nickName", "name", "display_name", "displayName"])
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
    if not follower_count:
        # 小红书搜索把粉丝数放在 sub_title(如 "Fans 160.8k" / "粉丝 16.5万"),没有独立数值字段,需解析。
        follower_count = fans_from_text(deep_first_str(item, ["sub_title", "subTitle", "fans_desc", "fansDesc"]))
    # 兜底校验:把"小红书号/用户ID 被当成粉丝数"(如 94351549807)和负数挡掉 → 粉丝未知。
    follower_known = 0 < follower_count <= MAX_PLAUSIBLE_FOLLOWERS
    if not follower_known:
        follower_count = 0
    return BloggerSearchResult(
        platform=platform,
        external_id=external_id,
        display_name=display_name,
        homepage_url=homepage_url,
        avatar_url=avatar_url,
        description=description,
        follower_count=follower_count,
        raw=item,
        follower_known=follower_known,
    )


def extract_user_profile(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    """从 get_user_info 原始返回里解析可覆盖的博主资料(刷新博主 / 采集时写笔记总数用)。

    拿不到的字段:display_name/avatar 给空串、follower 给 0、note_total 给 None(老实留空,不硬编)。
    """
    # 只认 nickname 系列键:小红书 user_info 的 interactions 列表里有 {name:"关注"/"粉丝"...},
    # 用通用 "name" 会把"关注"当成昵称(已踩坑),所以这里不用 name/display_name。
    display_name = first_str(payload, ["nickname", "nick_name", "nickName"]) or deep_first_str(payload, ["nickname", "nick_name", "nickName"])
    avatar_url = deep_first_str(payload, ["avatar", "avatar_url", "avatarUrl", "images", "image", "image_url"], list_keys=["url_list", "urlList"])
    follower_count = deep_first_int(payload, ["follower_count", "fans_count", "fansCount", "followerCount", "followers"])
    if not follower_count:
        follower_count = fans_from_text(deep_first_str(payload, ["sub_title", "subTitle", "fans_desc", "fansDesc"]))
    note_total = deep_first_int(
        payload,
        [
            "notes_count", "note_count", "noteCount", "notes_num", "notesNum",
            "aweme_count", "awemeCount", "works_count", "worksCount", "video_count", "videoCount", "note_total",
        ],
    )
    return {
        "display_name": display_name or "",
        "avatar_url": avatar_url or "",
        "follower_count": follower_count or 0,
        "note_total": note_total if note_total else None,
    }


def fans_from_text(text: str) -> int:
    """从 "Fans 160.8k" / "粉丝 16.5万" 这类文案里解析粉丝数。解析不出返回 0。

    防坑:当 sub_title 其实是"小红书号:9435154980"这类长串数字、又没有 万/k 单位时,
    不要把它当粉丝数(否则会出现 94351549807 这种离谱值)。
    """
    if not text:
        return 0
    match = re.search(r"([\d.]+)\s*([kKmMwW万亿])?", text)
    if not match:
        return 0
    raw_digits = match.group(1)
    try:
        num = float(raw_digits)
    except (TypeError, ValueError):
        return 0
    suffix = (match.group(2) or "").lower()
    # 无单位 + 一长串数字(>7 位)→ 基本是 ID/小红书号,不是粉丝数。
    if not suffix and len(raw_digits.replace(".", "")) > 7:
        return 0
    multiplier = {"k": 1_000, "m": 1_000_000, "w": 10_000, "万": 10_000, "亿": 100_000_000}.get(suffix, 1)
    return int(num * multiplier)


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
