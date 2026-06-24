from __future__ import annotations

import logging
import math
import statistics
import time
from typing import Any

from app.benchmark_discovery.context import BenchmarkContext
from app.blogger_distillation.search import BloggerSearchResult
from app.blogger_distillation.tikhub_client import first_int, first_str
from app.config import Settings
from app.schemas.benchmark import CandidateScore
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

# 默认权重/阈值;S6 会把同名项搬进 config + admin registry,这里用 getattr 兜底,先落地后可调。
_DEFAULTS = {
    "benchmark_weight_relevance": 0.4,
    "benchmark_weight_learnability": 0.25,
    "benchmark_weight_popularity": 0.25,
    "benchmark_weight_transferability": 0.1,
    "benchmark_inactive_days": 60,
}


def _cfg(settings: Settings, key: str) -> float:
    return float(getattr(settings, key, _DEFAULTS[key]))


def popularity_score(follower_count: int, like_samples: list[int]) -> float:
    """火爆度(0-100)= 0.5·粉丝分 + 0.5·互动分。纯规则,不调 LLM。"""
    follower = max(int(follower_count or 0), 0)
    follower_score = min(100.0, 20.0 * math.log10(follower + 1))  # 1k≈60 / 1w≈80 / 10w≈100
    likes = [int(x) for x in like_samples if x and int(x) > 0]
    if likes and follower > 0:
        rate = statistics.median(likes) / follower
        engagement_score = min(100.0, rate / 0.05 * 100.0)  # 互动率 5% 封顶满分
    elif likes:
        engagement_score = min(100.0, 20.0 * math.log10(statistics.median(likes) + 1))
    else:
        engagement_score = follower_score  # 无互动数据,退回粉丝分
    return round(0.5 * follower_score + 0.5 * engagement_score, 1)


def candidate_titles(recent: list[Any], limit: int = 10) -> list[str]:
    """从列表级候选的 raw 里尽力取近期标题(跨端点字段不一,best-effort)。"""
    titles: list[str] = []
    for cand in recent[:limit]:
        raw = getattr(cand, "raw", {}) or {}
        if not isinstance(raw, dict):
            continue
        title = first_str(raw, ["display_title", "title", "desc", "note_name", "caption", "content"])
        if not title:
            nested = raw.get("note_card")
            if isinstance(nested, dict):
                title = first_str(nested, ["display_title", "title", "desc"])
        if title and title.strip():
            titles.append(title.strip()[:60])
    return titles


def _first_epoch(raw: dict[str, Any]) -> int:
    """从 raw 里尽力取一个发布时间(秒)。毫秒自动转秒;取不到返回 0。"""
    for key in ("time", "create_time", "createTime", "timestamp", "publish_time", "last_update_time"):
        val = first_int(raw, [key])
        if val:
            return val // 1000 if val > 10_000_000_000 else val
    nested = raw.get("note_card")
    if isinstance(nested, dict):
        return _first_epoch(nested)
    return 0


def _is_active(recent: list[Any], inactive_days: float) -> bool:
    """活跃度 gate:近期还在更新则 True。取不到时间则不误判(默认 True)。"""
    newest = 0
    for cand in recent:
        raw = getattr(cand, "raw", {}) or {}
        if isinstance(raw, dict):
            newest = max(newest, _first_epoch(raw))
    if not newest:
        return True
    return (time.time() - newest) <= inactive_days * 86400


def _llm_eval(settings: Settings, ctx: BenchmarkContext, result: BloggerSearchResult, titles: list[str]) -> dict:
    titles_text = " / ".join(titles) if titles else "(未取到近期标题)"
    account_block = f"\n用户账号现状画像:\n{ctx.my_account_profile[:1200]}\n" if ctx.has_account else ""
    transfer_line = (
        '  "transferability": {"score": 0-100},  // 候选打法对"用户账号现状"是否够得着、可迁移\n'
        if ctx.has_account
        else ""
    )
    prompt = (
        "你在评估一个候选博主是否适合用户作为「对标学习对象」。用小白看得懂的中文。\n"
        f"用户想做:{ctx.niche}；受众:{ctx.audience or '未填'}；目标:{ctx.goal or '未填'}；"
        f"内容形式偏好:{ctx.content_form}\n"
        f"{account_block}"
        f"候选博主:{result.display_name}\n简介:{result.description or '(无)'}\n"
        f"粉丝:{result.follower_count}\n近期标题:{titles_text}\n\n"
        "请只输出 JSON:\n"
        "{\n"
        '  "relevance": {"score": 0-100, "reason": "方向是否契合用户想做的(一句话)"},\n'
        '  "learnability": {"score": 0-100, "reason": "是否适合照着学:方法论清晰、非纯靠个人资源/颜值/明星身份(一句话)"},\n'
        f"{transfer_line}"
        '  "summary": "一句话总评:推不推荐、为什么"\n'
        "}"
    )
    return create_json_response(settings, prompt)


def _sub_score(node: Any) -> float:
    if isinstance(node, dict):
        try:
            return max(0.0, min(100.0, float(node.get("score", 0))))
        except (TypeError, ValueError):
            return 0.0
    try:
        return max(0.0, min(100.0, float(node)))
    except (TypeError, ValueError):
        return 0.0


def _reason(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("reason", "")).strip()
    return ""


def evaluate_candidate(
    settings: Settings,
    ctx: BenchmarkContext,
    result: BloggerSearchResult,
    recent: list[Any],
    existing_blogger_id: int | None = None,
) -> CandidateScore:
    """评估单个候选:火爆度(规则)+ 方向契合/可对标性/(可迁移度) (LLM) → 综合分 + 依据。"""
    like_samples = [int(getattr(c, "like_count", 0) or 0) for c in recent]
    popularity = popularity_score(result.follower_count, like_samples)
    titles = candidate_titles(recent)
    active = _is_active(recent, _cfg(settings, "benchmark_inactive_days"))

    relevance = learnability = 0.0
    transferability: float | None = None
    reasons = {"relevance": "", "learnability": "", "summary": ""}
    try:
        llm = _llm_eval(settings, ctx, result, titles)
        relevance = _sub_score(llm.get("relevance"))
        learnability = _sub_score(llm.get("learnability"))
        if ctx.has_account and "transferability" in llm:
            transferability = _sub_score(llm.get("transferability"))
        reasons = {
            "relevance": _reason(llm.get("relevance")),
            "learnability": _reason(llm.get("learnability")),
            "summary": str(llm.get("summary", "")).strip(),
        }
    except Exception as exc:  # noqa: BLE001 - 单个候选评估失败不应让整批崩
        logger.warning("候选评估 LLM 失败:%s(%s)", result.display_name, exc)
        reasons["summary"] = "评估失败,仅供参考"

    w_rel = _cfg(settings, "benchmark_weight_relevance")
    w_learn = _cfg(settings, "benchmark_weight_learnability")
    w_pop = _cfg(settings, "benchmark_weight_popularity")
    w_trans = _cfg(settings, "benchmark_weight_transferability")
    if transferability is None:
        total = w_rel + w_learn + w_pop or 1.0
        overall = (relevance * w_rel + learnability * w_learn + popularity * w_pop) / total
    else:
        total = w_rel + w_learn + w_pop + w_trans or 1.0
        overall = (
            relevance * w_rel + learnability * w_learn + popularity * w_pop + transferability * w_trans
        ) / total
    if not active:
        overall *= 0.85  # 不活跃降权

    return CandidateScore(
        platform=result.platform,
        external_id=result.external_id,
        display_name=result.display_name,
        homepage_url=result.homepage_url,
        avatar_url=result.avatar_url,
        description=result.description,
        follower_count=result.follower_count,
        popularity=popularity,
        relevance=round(relevance, 1),
        learnability=round(learnability, 1),
        transferability=round(transferability, 1) if transferability is not None else None,
        overall=round(overall, 1),
        active=active,
        reasons=reasons,
        existing_blogger_id=existing_blogger_id,
    )
