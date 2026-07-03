"""博主档案编排:一键建档(五阶段)、档案聚合读、爆文归因入口、构建互斥。

建档 = 资料 → 全量笔记池 → 统计/轨迹(免费即时算) → 最新 N 篇升详情级(复用采集管线) → 自动蒸馏默认画像。
级联原则:免费的(统计/轨迹)读取时现算、池一变自然新;花钱的(画像/归因)只标过时,绝不自动重跑。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.blogger_dossier import compliance, habits, pool, stats, trajectory
from app.blogger_dossier.attribution import parse_attribution, run_attribution
from app.blogger_distillation.service.collection import refresh_blogger_profile, run_blogger_collection
from app.blogger_distillation.service.distillation import run_blogger_distillation
from app.blogger_distillation.service.events import record_task_event
from app.config import Settings
from app.models import BloggerDistillationRun, BloggerPost, BloggerProfile, BloggerSkill, BloggerSnapshot, OperationTask
from app.models.common import utc_now

logger = logging.getLogger(__name__)


def _get_blogger(db: Session, tenant_id: int, blogger_id: int) -> BloggerProfile:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    return blogger


def active_posts(db: Session, tenant_id: int, blogger_id: int) -> list[BloggerPost]:
    """在架笔记(统计/轨迹/归因的数据基):排除软删/下架/试采。"""
    return list(
        db.scalars(
            select(BloggerPost).where(
                BloggerPost.tenant_id == tenant_id,
                BloggerPost.blogger_id == blogger_id,
                BloggerPost.status == "active",
            )
        )
    )


# ============================ 构建互斥 ============================

def ensure_no_running_build(db: Session, blogger: BloggerProfile) -> None:
    """同一博主同时只允许一个构建类任务;锁指向的任务已结束则自愈清锁。"""
    task_id = (blogger.build_task_id or "").strip()
    if not task_id:
        return
    task = db.get(OperationTask, task_id)
    if task and str(task.status) in ("queued", "running", "cancel_requested"):
        raise ValueError("该博主已有构建任务进行中，请等它完成后再操作")
    blogger.build_task_id = ""
    db.commit()


# ============================ 一键建档 ============================

def build_dossier(db: Session, settings: Settings, task_id: str, tenant_id: int, blogger_id: int) -> dict[str, Any]:
    blogger = _get_blogger(db, tenant_id, blogger_id)
    ensure_no_running_build(db, blogger)
    blogger.build_task_id = task_id
    db.commit()
    try:
        # 阶段1 资料
        record_task_event(db, tenant_id, task_id, "建档·资料", "running", "拉取博主主页资料")
        blogger = refresh_blogger_profile(db, settings, tenant_id, blogger_id)
        record_task_event(
            db, tenant_id, task_id, "建档·资料", "succeeded",
            f"资料已更新：粉丝 {blogger.follower_count} · 平台笔记 {blogger.note_total if blogger.note_total is not None else '?'} 篇",
        )
        # 阶段2 全量笔记池
        sync = pool.sync_note_pool(db, settings, task_id, tenant_id, blogger, mode="full")
        # 阶段3 统计+轨迹(读取时现算;这里算一遍校验并回报)
        posts = active_posts(db, tenant_id, blogger_id)
        traj = trajectory.build_trajectory(posts)
        record_task_event(
            db, tenant_id, task_id, "建档·数据与轨迹", "succeeded",
            f"数据面板与成长轨迹已就绪：{len(posts)} 篇入池，{len(traj.get('bursts') or [])} 个爆发点",
        )
        # 阶段4 系统选样升详情级:最新 N 篇(基本盘/近期)+ 历史高赞 M 篇(爆文),两批并起来 = 分层样本。
        # 采样由系统定,用户不选;历史爆文进样是为了让画像学到"爆文怎么写"(选题思路那块最值钱的料)。
        recent_n = max(1, settings.dossier_default_full_count)
        hot_n = max(0, settings.dossier_hot_count)
        record_task_event(db, tenant_id, task_id, "建档·详情升级", "running",
                          f"升级最新 {recent_n} 篇 + 历史高赞 {hot_n} 篇为详情级(正文/转写/图文理解/评论)")
        run_blogger_collection(
            db, settings, task_id, tenant_id, blogger_id,
            sample_limit=recent_n, comments_per_post=20, asr_enabled=settings.asr_enabled,
            content_types=None, order="latest", fetch_all=False, backfill=True,
        )
        if hot_n:
            run_blogger_collection(
                db, settings, task_id, tenant_id, blogger_id,
                sample_limit=hot_n, comments_per_post=20, asr_enabled=settings.asr_enabled,
                content_types=None, order="top_liked", fetch_all=False, backfill=True,
            )
        # 阶段5 自动蒸馏唯一画像(系统选样的详情级笔记;去多画像 = 重蒸即覆盖,不建快照)
        ids = _sample_post_ids(db, tenant_id, blogger_id)
        distilled = False
        if len(ids) < settings.distill_min_samples:
            record_task_event(
                db, tenant_id, task_id, "建档·创作画像", "succeeded",
                f"详情级笔记仅 {len(ids)} 篇（<{settings.distill_min_samples}），本次跳过自动蒸馏，可稍后手动蒸馏",
            )
        else:
            run_blogger_distillation(
                db, settings, task_id, tenant_id, blogger_id,
                post_ids=ids, source="dossier", snapshot_id=None, mode="A",
            )
            distilled = True
        return {"pool": sync, "full_selected": len(ids), "distilled": distilled}
    finally:
        db.rollback()  # 子流程失败时残留的脏事务先回滚,确保锁一定能清掉
        locked = db.get(BloggerProfile, blogger_id)
        if locked is not None:
            locked.build_task_id = ""
            db.commit()


def _sample_post_ids(db: Session, tenant_id: int, blogger_id: int) -> list[int]:
    """系统选样 = 建档已升级为详情级的全部在架笔记(最新 N 批 + 历史高赞批)。

    两批升级已把样本定住(近期基本盘 + 历史爆文),这里全取即可;下游证据装配器再按预算截断。
    """
    rows = db.scalars(
        select(BloggerPost)
        .where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger_id,
            BloggerPost.status == "active",
            BloggerPost.detail_level == "full",
        )
        .order_by(BloggerPost.published_at.desc().nullslast(), BloggerPost.created_at.desc())
    )
    return [p.id for p in rows]


def sync_pool(db: Session, settings: Settings, task_id: str, tenant_id: int, blogger_id: int, *, mode: str) -> dict[str, Any]:
    """笔记池手动同步(增量/全量校准),带构建互斥锁。级联:统计/轨迹读取时现算,天然更新。"""
    blogger = _get_blogger(db, tenant_id, blogger_id)
    ensure_no_running_build(db, blogger)
    blogger.build_task_id = task_id
    db.commit()
    try:
        return pool.sync_note_pool(db, settings, task_id, tenant_id, blogger, mode=mode)
    finally:
        db.rollback()
        locked = db.get(BloggerProfile, blogger_id)
        if locked is not None:
            locked.build_task_id = ""
            db.commit()


# ============================ 归因入口 ============================

def run_attribution_for_blogger(db: Session, settings: Settings, tenant_id: int, blogger_id: int) -> dict[str, Any]:
    blogger = _get_blogger(db, tenant_id, blogger_id)
    posts = active_posts(db, tenant_id, blogger_id)
    if not posts:
        raise ValueError("笔记池为空，请先构建博主画像")
    result = run_attribution(settings, posts, trajectory.build_trajectory(posts))
    blogger.attribution_json = json.dumps(result, ensure_ascii=False)
    db.commit()
    return result


# ============================ 档案聚合读 ============================

def dossier_overview(db: Session, settings: Settings, tenant_id: int, blogger_id: int) -> dict[str, Any]:
    blogger = _get_blogger(db, tenant_id, blogger_id)
    posts = active_posts(db, tenant_id, blogger_id)
    building = _building_status(db, blogger)
    # 数据面板要展示「共 N 篇 · 已收录 M（覆盖率）」和账号级获赞收藏,把这两项平台事实注入 stats。
    stats_payload = stats.account_stats(posts) if posts else None
    if stats_payload is not None:
        stats_payload["note_total"] = blogger.note_total
        stats_payload["liked_collected_count"] = blogger.liked_collected_count
        stats_payload["reached_end"] = bool(blogger.pool_reached_end)
    return {
        "blogger_id": blogger.id,
        "pool": {
            "total": len(posts),
            "note_total": blogger.note_total,
            "full_count": sum(1 for p in posts if p.detail_level == "full"),
            "list_count": sum(1 for p in posts if p.detail_level != "full"),
            "synced_at": blogger.pool_synced_at,
            "reached_end": bool(blogger.pool_reached_end),
        },
        "stats": stats_payload,
        "habits": habits.operating_habits(posts) if posts else None,
        "compliance": (
            compliance.scan_pool(blogger.platform, blogger.niche, [t["name"] for t in blogger.tags], posts)
            if posts else None
        ),
        "trajectory": trajectory.build_trajectory(posts) if posts else None,
        "attribution": parse_attribution(blogger.attribution_json),
        "portraits": _portraits(db, settings, tenant_id, blogger_id),
        "building": building,
    }


def _building_status(db: Session, blogger: BloggerProfile) -> dict[str, Any] | None:
    task_id = (blogger.build_task_id or "").strip()
    if not task_id:
        return None
    task = db.get(OperationTask, task_id)
    if not task or str(task.status) not in ("queued", "running", "cancel_requested"):
        return None
    return {"task_id": task_id, "status": str(task.status), "message": task.message}


def _portraits(db: Session, settings: Settings, tenant_id: int, blogger_id: int) -> list[dict[str, Any]]:
    """active 画像(可多个)+ 过时判定:蒸馏后池里新增 ≥N 篇 或 距蒸馏超 N 天。过时≠失效,照常可用。"""
    skills = list(
        db.scalars(
            select(BloggerSkill)
            .where(BloggerSkill.tenant_id == tenant_id, BloggerSkill.blogger_id == blogger_id, BloggerSkill.status == "active")
            .order_by(BloggerSkill.created_at.desc())
        )
    )
    out: list[dict[str, Any]] = []
    for skill in skills:
        run = db.get(BloggerDistillationRun, skill.run_id)
        distilled_at: datetime | None = run.created_at if run else skill.created_at
        new_since = int(
            db.scalar(
                select(func.count(BloggerPost.id)).where(
                    BloggerPost.tenant_id == tenant_id,
                    BloggerPost.blogger_id == blogger_id,
                    BloggerPost.status == "active",
                    BloggerPost.created_at > distilled_at,
                )
            )
            or 0
        )
        age_days = max(0, int((utc_now() - distilled_at).total_seconds() // 86400)) if distilled_at else 0
        snapshot = db.get(BloggerSnapshot, run.snapshot_id) if run and run.snapshot_id else None
        try:
            lanes = [x for x in json.loads(skill.scope_json or "[]") if isinstance(x, str)]
        except (json.JSONDecodeError, TypeError):
            lanes = []
        out.append(
            {
                "skill_id": skill.id,
                "run_id": skill.run_id,
                "name": skill.name,
                "distilled_at": distilled_at,
                "sample_count": run.sample_count if run else 0,
                "snapshot_id": run.snapshot_id if run else None,
                "snapshot_name": snapshot.name if snapshot else "",
                "lanes": lanes,
                "new_posts_since": new_since,
                "stale": new_since >= settings.portrait_stale_new_posts or age_days > settings.portrait_stale_days,
            }
        )
    return out
