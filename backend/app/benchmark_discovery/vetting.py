"""账号核验:对广召回来的候选,逐个补取「简介 + 互动数 + 近期笔记标题」,再用 LLM 判定与领域的相关度。

为什么要这步:广召回(搜用户/搜笔记取作者)只能证明"写过沾边的内容",证明不了"这个账号本身就是做这个领域的"
——泛博主偶尔写一条就被带出来。这里像人一样点进主页看(简介+最近发什么),才判得准。顺带把硬数据取回来填卡片。

取数失败/LLM 失败都有兜底:取不到资料就按召回时的信息走;LLM 判不了就用规则(领域词命中数)兜。
"""

from __future__ import annotations

import concurrent.futures
import logging

from app.blogger_distillation.endpoint_router import DOUYIN_ENDPOINT_POOLS, XHS_ENDPOINT_POOLS, EndpointRouter
from app.blogger_distillation.search import deep_first_str, fans_from_text
from app.blogger_distillation.tikhub_client import TikHubBaseClient
from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)


def _router(settings: Settings, platform: str) -> EndpointRouter:
    base = TikHubBaseClient(settings, missing_key_message="未配置 TIKHUB_API_KEY，无法核验账号")
    pools = DOUYIN_ENDPOINT_POOLS if platform == "douyin" else XHS_ENDPOINT_POOLS
    return EndpointRouter(base._get, pools)


def _find_interactions(node) -> list[dict]:
    """递归找小红书 user_info 里的 interactions 列表(含 关注/粉丝/获赞与收藏)。"""
    if isinstance(node, dict):
        for v in node.values():
            found = _find_interactions(v)
            if found:
                return found
    elif isinstance(node, list):
        if any(isinstance(x, dict) and x.get("type") in ("fans", "follows", "interaction") for x in node):
            return [x for x in node if isinstance(x, dict)]
        for x in node:
            found = _find_interactions(x)
            if found:
                return found
    return []


def _notes_titles(payload, limit: int) -> list[str]:
    """从 user_notes 响应里取近期标题(跨端点结构不一,best-effort)。"""
    node = payload
    for _ in range(6):  # 逐层下钻找 notes 列表
        if isinstance(node, dict):
            if isinstance(node.get("notes"), list):
                node = node["notes"]
                break
            node = node.get("data")
        else:
            break
    titles: list[str] = []
    if isinstance(node, list):
        for n in node:
            if isinstance(n, dict):
                t = deep_first_str(n, ["display_title", "title", "desc"])
                if t:
                    titles.append(t[:50])
            if len(titles) >= limit:
                break
    return titles


def fetch_detail(settings: Settings, platform: str, user_id: str, xsec_token: str, recent_notes: int) -> dict:
    """补取账号资料:简介 / IP / 粉丝 / 获赞与收藏 / 近期笔记标题。任一失败 → 该字段留空。"""
    out = {"bio": "", "ip_location": "", "follower": 0, "like_collect": 0, "titles": []}
    router = _router(settings, platform)
    try:
        info = router.call("user_info", {"user_id": user_id, "xsec_token": xsec_token})
        out["bio"] = deep_first_str(info, ["desc", "signature", "description"])
        out["ip_location"] = deep_first_str(info, ["ipLocation", "ip_location"])
        for it in _find_interactions(info):
            count = fans_from_text(str(it.get("count") or it.get("i18nCount") or "0"))
            if it.get("type") == "fans":
                out["follower"] = count
            elif it.get("type") == "interaction":
                out["like_collect"] = count
    except Exception as exc:  # noqa: BLE001
        logger.warning("核验·取资料失败 uid=%s:%s", user_id, exc)
    try:
        notes = router.call("user_notes", {"user_id": user_id, "cursor": "", "num": recent_notes, "xsec_token": xsec_token})
        out["titles"] = _notes_titles(notes, recent_notes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("核验·取笔记失败 uid=%s:%s", user_id, exc)
    return out


def _rule_relevance(domains: list[str], bio: str, titles: list[str]) -> tuple[int, int]:
    """LLM 不可用时的兜底:领域词在简介+标题里的命中数 → 粗相关度。返回 (relevance, hit_count)。"""
    toks = [t for d in domains for t in (d, *d.split()) if len(t) >= 2]
    blob = bio + " " + " ".join(titles)
    hit_count = sum(1 for t in titles if any(tok in t for tok in toks))
    bio_hit = any(tok in blob for tok in toks)
    rel = min(100, hit_count * 25 + (20 if bio_hit else 0))
    return rel, hit_count


def _hit_count(domains: list[str], titles: list[str]) -> int:
    toks = [t for d in domains for t in (d, *d.split()) if len(t) >= 2]
    return sum(1 for t in titles if any(tok in t for tok in toks))


def vet_candidates(
    settings: Settings, platform: str, items: list[dict], domains: list[str], *, on_progress=None
) -> dict[str, dict]:
    """对候选(items: [{external_id, display_name, xsec_token}]) 逐个核验,返回 {external_id -> 核验数据}。

    核验数据:bio / ip_location / follower / like_collect / titles / hit_count / relevance / relevance_reason。
    """
    conc = int(getattr(settings, "discovery_vet_concurrency", 5) or 5)
    recent = int(getattr(settings, "discovery_recent_notes", 8) or 8)
    details: dict[str, dict] = {}

    def work(it: dict) -> tuple[str, dict]:
        return it["external_id"], fetch_detail(settings, platform, it["external_id"], it.get("xsec_token", ""), recent)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, conc)) as ex:
        for ext_id, detail in ex.map(work, items):
            details[ext_id] = detail
    if on_progress:
        on_progress("核验账号", f"已查 {len(details)} 个账号的主页与近期笔记")

    # 一次 LLM 批量判定相关度(看昵称+简介+近期标题)。失败 → 规则兜底。
    rel_map = _llm_relevance(settings, domains, items, details)
    out: dict[str, dict] = {}
    for it in items:
        ext = it["external_id"]
        d = details.get(ext, {})
        titles = d.get("titles", [])
        rel, reason = rel_map.get(ext, (None, ""))
        if rel is None:
            rel, _ = _rule_relevance(domains, d.get("bio", ""), titles)
            reason = "按领域词命中估算"
        out[ext] = {
            "bio": d.get("bio", ""), "ip_location": d.get("ip_location", ""),
            "follower": d.get("follower", 0), "like_collect": d.get("like_collect", 0),
            "titles": titles[:6], "hit_count": _hit_count(domains, titles),
            "relevance": int(rel), "relevance_reason": reason,
        }
    return out


def _llm_relevance(settings: Settings, domains: list[str], items: list[dict], details: dict[str, dict]) -> dict[str, tuple[int, str]]:
    """一次性判定所有候选与领域的相关度。返回 {external_id -> (relevance, reason)};失败返回空(调用方走规则)。"""
    lines = []
    idx_to_ext: dict[int, str] = {}
    for i, it in enumerate(items):
        ext = it["external_id"]
        d = details.get(ext, {})
        idx_to_ext[i] = ext
        titles = "；".join(d.get("titles", [])[:6]) or "(没取到)"
        lines.append(f"[{i}] 昵称:{it.get('display_name', '')} 简介:{d.get('bio', '') or '(空)'} "
                     f"IP:{d.get('ip_location', '') or '?'} 最近笔记:{titles}")
    if not lines:
        return {}
    prompt = (
        f"用户要找「{('、'.join(domains))}」领域的对标博主。下面每个候选给了昵称、简介、IP、最近笔记标题。\n"
        "判断每个账号**本身是不是真的在做这个领域**(只是偶尔提一句不算),给 0-100 相关度和一句理由。\n\n"
        + "\n".join(lines)
        + '\n\n只输出 JSON:{"scores":[{"i":0,"relevance":0-100,"reason":"一句话"}]}'
    )
    try:
        data = create_json_response(settings, prompt)
        raw = data.get("scores") if isinstance(data, dict) else None
        out: dict[str, tuple[int, str]] = {}
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            i = item.get("i")
            ext = idx_to_ext.get(int(i)) if isinstance(i, (int, float)) else None
            if ext is None:
                continue
            try:
                rel = max(0, min(100, int(float(item.get("relevance", 0)))))
            except (TypeError, ValueError):
                rel = 0
            out[ext] = (rel, str(item.get("reason", "")).strip())
        logger.info("泛搜索·相关度判定 领域=%s 候选=%d 判出=%d", domains, len(items), len(out))
        return out
    except Exception as exc:  # noqa: BLE001 - 判不了 → 规则兜底
        logger.warning("泛搜索·相关度判定失败,走规则兜底:%s(%s)", exc, type(exc).__name__)
        return {}
