"""博主内容标签:采集时 LLM 语义提炼(auto) + 用户手填(manual)的生成与合并。

标签存于 ``BloggerProfile.tags_json``,元素 ``{"name": str, "source": "auto"|"manual"}``。
更新策略:
- 采集端 ``merge_tags`` —— 每次重算并**替换全部 auto**,**保留全部 manual**。
- 编辑端 ``set_manual_tags`` —— 用户手填时**替换全部 manual**,**保留全部 auto**。
两端都对名称做去重(auto 与 manual 不重名,manual 优先)。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.models import BloggerPost, BloggerProfile
from app.prompts import anti_injection
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

_MAX_TAG_LEN = 12
_TOP_POSTS = 12
_PLATFORM_LABEL = {"xhs": "小红书", "douyin": "抖音"}


def _load(existing_json: str) -> list[dict[str, str]]:
    try:
        data = json.loads(existing_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _split(existing_json: str) -> tuple[list[dict[str, str]], set[str]]:
    """返回 (manual 标签列表, 已用名小写集合)。"""
    manual: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in _load(existing_json):
        if not isinstance(item, dict) or item.get("source") != "manual":
            continue
        name = str(item.get("name", "")).strip()
        if name and name.lower() not in seen:
            manual.append({"name": name, "source": "manual"})
            seen.add(name.lower())
    return manual, seen


def _clean_names(raw: Any, *, limit: int, exclude: set[str]) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen = set(exclude)
    for item in raw:
        name = str(item).strip().lstrip("#").strip()
        if not name or len(name) > _MAX_TAG_LEN:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def merge_tags(existing_json: str, new_auto: list[str], *, limit: int = 6) -> str:
    """采集端:替换全部 auto,保留全部 manual(auto 名与 manual 去重)。"""
    manual, manual_names = _split(existing_json)
    auto_names = _clean_names(new_auto, limit=limit, exclude=manual_names)
    auto = [{"name": name, "source": "auto"} for name in auto_names]
    return json.dumps(manual + auto, ensure_ascii=False)


def set_manual_tags(existing_json: str, manual_names: list[str], *, limit: int = 12) -> str:
    """编辑端:替换全部 manual,保留全部 auto(manual 优先,auto 与之去重)。"""
    clean_manual = _clean_names(manual_names, limit=limit, exclude=set())
    manual_keys = {n.lower() for n in clean_manual}
    auto: list[dict[str, str]] = []
    seen = set(manual_keys)
    for item in _load(existing_json):
        if not isinstance(item, dict) or item.get("source") != "auto":
            continue
        name = str(item.get("name", "")).strip()
        if name and name.lower() not in seen:
            auto.append({"name": name, "source": "auto"})
            seen.add(name.lower())
    manual = [{"name": name, "source": "manual"} for name in clean_manual]
    return json.dumps(manual + auto, ensure_ascii=False)


def generate_auto_tags(
    settings: Settings,
    blogger: BloggerProfile,
    posts: list[BloggerPost],
    stats: dict[str, Any],
    *,
    model: str | None = None,
    limit: int = 6,
) -> list[str]:
    """用 LLM 从代表性内容提炼 3~limit 个内容主题标签。单次调用,不做多轮修订。"""
    top = sorted(posts, key=lambda p: p.score or 0, reverse=True)[:_TOP_POSTS]
    lines: list[str] = []
    for post in top:
        body = (post.body_text or "").strip().replace("\n", " ")
        lines.append(f"- 标题:{post.title or '(无标题)'};正文:{body[:120]}")
    samples = "\n".join(lines) or "(无样本)"
    hot = [str(h.get("tag")) for h in (stats.get("frequent_hashtags") or []) if h.get("tag")][:15]
    hashtag_hint = "、".join(hot) or "(无)"
    platform_name = _PLATFORM_LABEL.get(blogger.platform, blogger.platform)
    system = (
        "你是内容运营分析助手。从给定的博主代表性内容里提炼"
        f"**内容主题标签**,概括这个账号做什么领域/题材。\n"
        "<rules>\n"
        f"- 提炼 3-{limit} 个标签,每个 2-6 个汉字,简洁、互不重复;不要带 # 号;不要营销口号或情绪词。\n"
        f"- {anti_injection('<samples>', '<platform_hashtags>')}\n"
        "</rules>\n"
        '<output_schema>只输出 JSON:{"tags": ["标签1", "标签2", ...]}</output_schema>'
    )
    prompt = (
        f"博主「{blogger.display_name}」· 平台:{platform_name}\n"
        f"<samples>\n{samples}\n</samples>\n"
        f"<platform_hashtags>(仅供参考,可借鉴但不要照搬营销词)\n{hashtag_hint}\n</platform_hashtags>"
    )
    data = create_json_response(settings, prompt, model=model, system=system)
    return _clean_names(data.get("tags"), limit=limit, exclude=set())
