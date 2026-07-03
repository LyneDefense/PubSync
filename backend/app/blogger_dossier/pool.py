"""笔记池(档案物理层):列表级行的 upsert 与增量/全量同步。

笔记池 = ``BloggerPost`` 一张表、两个详情级别:
- **list**:仅列表卡数据(标题/时间/互动/浏览),全量笔记都有 —— 统计/轨迹的数据源;
- **full**:抓过详情(正文/转写/图文理解/评论),蒸馏选中的那部分。只升不降。

此前列表候选"没选中就丢弃",这里改为全量落库;老笔记路过时顺带刷新互动(近期笔记恰是仍在变化的)。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.blogger_distillation.service.events import record_task_event
from app.blogger_distillation.service.extract.post import extract_note_key, interaction_score
from app.blogger_distillation.tikhub_client import XhsPostCandidate, build_platform_client
from app.blogger_distillation.tikhub_client.parsers import first_str
from app.config import Settings
from app.models import BloggerPost, BloggerProfile
from app.models.common import utc_now

logger = logging.getLogger(__name__)


def refresh_from_candidate(post: BloggerPost, candidate: XhsPostCandidate) -> None:
    """用列表卡刷新一行(新旧笔记通用):互动>0 才覆盖;补时间;token 用最新;不降详情级。"""
    if candidate.like_count:
        post.like_count = candidate.like_count
    if candidate.favorite_count:
        post.favorite_count = candidate.favorite_count
    if candidate.comment_count:
        post.comment_count = candidate.comment_count
    if candidate.share_count:
        post.share_count = candidate.share_count
    if candidate.view_count:
        post.view_count = candidate.view_count
    if candidate.published_at and not post.published_at:
        post.published_at = candidate.published_at
    if candidate.xsec_token:
        post.xsec_token = candidate.xsec_token
    post.score = interaction_score(post.like_count, post.favorite_count, post.comment_count, post.share_count)
    post.last_seen_at = utc_now()


def upsert_list_candidates(
    db: Session, tenant_id: int, blogger: BloggerProfile, candidates: list[XhsPostCandidate]
) -> dict[str, int]:
    """把一批列表卡 upsert 进池:已有(按 note_key/external_id)→ 刷新;没有 → 建 list 级行。不 commit。"""
    posts = list(db.scalars(select(BloggerPost).where(BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger.id)))
    by_key = {p.note_key: p for p in posts if p.note_key}
    by_ext = {p.external_id: p for p in posts}
    created = refreshed = 0
    for candidate in candidates:
        key = extract_note_key(candidate.raw, {}, candidate.external_id)
        post = by_key.get(key) or by_ext.get(candidate.external_id)
        if post is not None:
            refresh_from_candidate(post, candidate)
            refreshed += 1
            continue
        post = _new_list_row(tenant_id, blogger, candidate, key)
        db.add(post)
        by_key[key] = post
        by_ext[candidate.external_id] = post
        created += 1
    db.flush()
    return {"new": created, "refreshed": refreshed}


def _new_list_row(tenant_id: int, blogger: BloggerProfile, candidate: XhsPostCandidate, note_key: str) -> BloggerPost:
    title = first_str(candidate.raw, ["display_title", "title"]) or "未命名笔记"
    return BloggerPost(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        platform=blogger.platform,
        external_id=candidate.external_id,
        note_key=note_key,
        url=first_str(candidate.raw, ["share_url", "url"]),
        title=title[:500],
        content_type=candidate.note_type if candidate.note_type in ("image", "video") else "image",
        like_count=candidate.like_count,
        favorite_count=candidate.favorite_count,
        comment_count=candidate.comment_count,
        share_count=candidate.share_count,
        view_count=candidate.view_count,
        published_at=candidate.published_at,
        score=interaction_score(candidate.like_count, candidate.favorite_count, candidate.comment_count, candidate.share_count),
        detail_level="list",
        xsec_token=candidate.xsec_token,
        status="active",
        last_seen_at=utc_now(),
        # list 级不参与 ASR/视觉补采判定;升级详情时由 normalize_post 重置为 pending。
        asr_status="not_required",
        vision_status="not_required",
    )


def sync_note_pool(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger: BloggerProfile,
    *,
    mode: str = "full",
) -> dict[str, Any]:
    """拉主页列表 → upsert 笔记池。full=翻到底(或安全上限);incremental=尾部连续遇到已知笔记即停。"""
    client = build_platform_client(settings, blogger.platform)
    known_ids = set(
        db.scalars(select(BloggerPost.external_id).where(BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger.id))
    )
    should_stop = None
    if mode == "incremental" and known_ids:
        streak = max(5, settings.dossier_incremental_known_streak)

        def should_stop(cands: list[XhsPostCandidate]) -> bool:  # noqa: F811 - 条件定义
            tail = cands[-streak:]
            return len(tail) >= streak and all(c.external_id in known_ids for c in tail)

    record_task_event(db, tenant_id, task_id, "笔记池同步", "running", f"{'全量' if mode == 'full' else '增量'}拉取主页笔记列表…")
    result = client.get_user_notes(blogger.homepage_url, settings.candidate_pool_cap, blogger.external_id, should_stop=should_stop)
    counts = upsert_list_candidates(db, tenant_id, blogger, result.candidates)
    blogger.pool_synced_at = utc_now()
    if mode == "full" or result.reached_end:
        blogger.pool_reached_end = result.reached_end
    blogger.sample_count = int(
        db.scalar(
            select(func.count(BloggerPost.id)).where(
                BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger.id, BloggerPost.status != "delisted"
            )
        )
        or 0
    )
    db.commit()
    summary = {"seen": len(result.candidates), "new": counts["new"], "refreshed": counts["refreshed"], "reached_end": result.reached_end}
    record_task_event(
        db, tenant_id, task_id, "笔记池同步", "succeeded",
        f"笔记池已同步:看到 {summary['seen']} 篇,新入池 {summary['new']},刷新 {summary['refreshed']}"
        + ("(已翻到第一篇)" if result.reached_end else "(未翻到底,早期部分缺失)"),
        summary,
    )
    return summary
