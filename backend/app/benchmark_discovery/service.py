from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmark_discovery.context import build_context
from app.benchmark_discovery.engine import evaluate_candidate
from app.benchmark_discovery.querygen import expand_search_terms
from app.blogger_distillation.search import (
    BloggerSearchResult,
    extract_user_profile,
    search_bloggers,
)
from app.blogger_distillation.service import record_task_event
from app.blogger_distillation.service.collection import build_collection_client
from app.config import Settings
from app.models import BenchmarkRecommendationRun, BloggerPost, BloggerProfile
from app.services.ai_service import AIServiceError, is_ai_enabled

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "benchmark_candidate_pool_cap": 12,
    "benchmark_list_sample": 12,
    "benchmark_search_terms_max": 5,
}


def _cfg_int(settings: Settings, key: str) -> int:
    return int(getattr(settings, key, _DEFAULTS[key]))


@dataclass
class _DbCandidate:
    """把库内已采笔记包装成 engine 认得的"列表级候选"(只需 like_count + raw)。"""

    like_count: int
    raw: dict[str, Any] = field(default_factory=dict)


def _dedupe_cap(results: list[BloggerSearchResult], cap: int) -> list[BloggerSearchResult]:
    seen: set[str] = set()
    out: list[BloggerSearchResult] = []
    for r in results:
        key = (r.external_id or r.homepage_url or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= cap:
            break
    return out


def _find_existing(db: Session, tenant_id: int, platform: str, external_id: str, homepage_url: str) -> BloggerProfile | None:
    """库里已有这个人(任意 account_type)则返回,用于复用已采笔记、零新增调用。"""
    stmt = select(BloggerProfile).where(
        BloggerProfile.tenant_id == tenant_id, BloggerProfile.platform == platform
    )
    for profile in db.scalars(stmt):
        if external_id and profile.external_id == external_id:
            return profile
        if homepage_url and profile.homepage_url == homepage_url:
            return profile
    return None


def _recent_from_db(db: Session, tenant_id: int, blogger_id: int, limit: int) -> list[_DbCandidate]:
    stmt = (
        select(BloggerPost)
        .where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger_id,
            BloggerPost.status == "active",
        )
        .order_by(BloggerPost.id.desc())
    )
    posts = list(db.scalars(stmt))[:limit]
    out: list[_DbCandidate] = []
    for post in posts:
        raw: dict[str, Any] = {"title": post.title or ""}
        if post.published_at:
            raw["time"] = int(post.published_at.timestamp())
        out.append(_DbCandidate(like_count=post.like_count or 0, raw=raw))
    return out


def _fetch_recent_live(settings: Settings, platform: str, homepage_url: str, external_id: str, limit: int) -> list[Any]:
    """对未入库的候选拉一页列表级笔记(便宜)。失败则返回空,评估降级为只用粉丝数。"""
    try:
        client = build_collection_client(settings, platform)
        result = client.get_user_notes(homepage_url, limit, external_id or None)
        return list(result.candidates)
    except Exception as exc:  # noqa: BLE001 - 列表取数失败不阻断评估
        logger.warning("候选列表级取数失败,降级评估:%s(%s)", homepage_url, exc)
        return []


def _resolve_candidate_from_url(settings: Settings, platform: str, homepage_url: str) -> BloggerSearchResult:
    """URL 粘贴评分:拉 user_info 拼成候选。"""
    client = build_collection_client(settings, platform)
    payload = client.get_user_info(homepage_url)
    profile = extract_user_profile(platform, payload)
    return BloggerSearchResult(
        platform=platform,
        external_id="",
        display_name=profile.get("display_name", "") or "该博主",
        homepage_url=homepage_url,
        avatar_url=profile.get("avatar_url", ""),
        description="",
        follower_count=int(profile.get("follower_count") or 0),
        raw=payload,
    )


def _score_one(
    db: Session,
    settings: Settings,
    ctx,
    tenant_id: int,
    platform: str,
    result: BloggerSearchResult,
):
    """对一个候选取数(库内复用 / 否则列表级)→ 评估。"""
    existing = _find_existing(db, tenant_id, platform, result.external_id, result.homepage_url)
    list_sample = _cfg_int(settings, "benchmark_list_sample")
    if existing and (existing.sample_count or 0) > 0:
        recent: list[Any] = _recent_from_db(db, tenant_id, existing.id, list_sample)
    else:
        recent = _fetch_recent_live(settings, platform, result.homepage_url, result.external_id, list_sample)
    return evaluate_candidate(
        settings, ctx, result, recent, existing_blogger_id=existing.id if existing else None
    )


def run_recommendation(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    platform: str,
    intent: dict,
    my_account_id: int | None = None,
) -> BenchmarkRecommendationRun:
    """智能推荐:意图→搜索词→候选池→逐个评估→排序,结果写入 BenchmarkRecommendationRun。"""
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    if not str(intent.get("niche", "")).strip():
        raise ValueError("请填写你的领域/赛道")

    run = BenchmarkRecommendationRun(
        tenant_id=tenant_id,
        platform=platform,
        kind="recommend",
        intent_json=json.dumps(intent, ensure_ascii=False),
        my_account_id=my_account_id,
        task_id=task_id,
        status="running",
        candidates_json="[]",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    ctx = build_context(db, tenant_id, platform, intent, my_account_id)
    record_task_event(db, tenant_id, task_id, "理解意图", "succeeded", f"领域「{ctx.niche}」" + ("(已结合你的账号)" if ctx.has_account else ""))

    terms = expand_search_terms(settings, ctx, _cfg_int(settings, "benchmark_search_terms_max"))
    record_task_event(db, tenant_id, task_id, "扩展搜索词", "succeeded", "、".join(terms) or ctx.niche)

    pool: list[BloggerSearchResult] = []
    for term in terms:
        try:
            pool.extend(search_bloggers(settings, platform, term))
        except Exception as exc:  # noqa: BLE001 - 单个搜索词失败不阻断
            logger.warning("搜索词「%s」失败:%s", term, exc)
    candidates = _dedupe_cap(pool, _cfg_int(settings, "benchmark_candidate_pool_cap"))
    record_task_event(db, tenant_id, task_id, "汇总候选", "succeeded", f"去重后 {len(candidates)} 个候选,开始逐个评估")

    scores = []
    for idx, result in enumerate(candidates, start=1):
        scores.append(_score_one(db, settings, ctx, tenant_id, platform, result))
        record_task_event(db, tenant_id, task_id, "评估候选", "running", f"已评估 {idx}/{len(candidates)}:{result.display_name}")

    scores.sort(key=lambda c: c.overall, reverse=True)
    run.candidates_json = json.dumps([c.model_dump() for c in scores], ensure_ascii=False)
    run.status = "succeeded"
    db.commit()
    db.refresh(run)
    return run


def evaluate_one(
    db: Session,
    settings: Settings,
    tenant_id: int,
    platform: str,
    intent: dict,
    my_account_id: int | None,
    candidate: dict | None,
    homepage_url: str | None,
):
    """单博主评分(同步):候选来自搜索结果或粘贴链接。"""
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    if not str(intent.get("niche", "")).strip():
        raise ValueError("请填写你的领域/赛道")

    if candidate:
        result = BloggerSearchResult(
            platform=platform,
            external_id=str(candidate.get("external_id", "")),
            display_name=str(candidate.get("display_name", "")) or "该博主",
            homepage_url=str(candidate.get("homepage_url", "")),
            avatar_url=str(candidate.get("avatar_url", "")),
            description=str(candidate.get("description", "")),
            follower_count=int(candidate.get("follower_count") or 0),
            raw=candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {},
        )
    elif homepage_url:
        result = _resolve_candidate_from_url(settings, platform, homepage_url)
    else:
        raise ValueError("请选择一个候选博主或粘贴主页链接")

    ctx = build_context(db, tenant_id, platform, intent, my_account_id)
    return _score_one(db, settings, ctx, tenant_id, platform, result)
