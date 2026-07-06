"""效果看板聚合：用现有数据回答「用了 PubSync 帮到了什么」。

两层：
- A 层 overview：租户级，和有没有「我的账号」无关——计数/耗时/对标库/创作发布/省时/相似度趋近。
- B 层 account：按某个「我的账号」——创作发布/省时/爆款率/模态对比；growth 是涨粉时序(依赖每日快照)。

诚实原则：涨粉只呈现相关性(曲线 + 使用事件打点 + 活跃/沉默对比)，不宣称因果。
详见 docs/效果看板_方案设计.md。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    AccountMetricSnapshot,
    BloggerPost,
    BloggerProfile,
    OperationTask,
    XhsPublishPackage,
)

# 活动类型 → 中文名（看板展示用）
ACTIVITY_LABELS: dict[str, str] = {
    "blogger_collection": "采集",
    "blogger_distillation": "蒸馏",
    "xhs_package_draft": "AI 创作",
    "account_audit": "账号体检",
    "benchmark_recommend": "找对标",
}
# overview 计数卡按这个顺序展示的核心三项
CORE_ACTIVITIES = ["blogger_collection", "blogger_distillation", "xhs_package_draft"]


def _since(range_key: str) -> datetime | None:
    days = {"7d": 7, "30d": 30}.get(range_key)
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _interactions(post: BloggerPost) -> int:
    return int(post.like_count or 0) + int(post.comment_count or 0) + int(post.share_count or 0)


def _activity_stats(db: Session, tenant_id: int, since: datetime | None) -> list[dict]:
    """各 task_type 的成功次数 + 平均耗时(秒)。耗时用 updated_at-created_at(succeeded)。"""
    stmt = select(OperationTask).where(OperationTask.tenant_id == tenant_id)
    if since is not None:
        stmt = stmt.where(OperationTask.created_at >= since)
    rows = list(db.scalars(stmt))
    agg: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_seconds": 0.0, "succeeded": 0})
    for t in rows:
        a = agg[t.task_type]
        a["count"] += 1
        if str(getattr(t.status, "value", t.status)) == "succeeded":
            a["succeeded"] += 1
            if t.created_at and t.updated_at:
                a["total_seconds"] += max(0.0, (t.updated_at - t.created_at).total_seconds())
    out: list[dict] = []
    for key in CORE_ACTIVITIES:
        a = agg.get(key, {"count": 0, "succeeded": 0, "total_seconds": 0.0})
        succ = a["succeeded"]
        out.append({
            "key": key,
            "label": ACTIVITY_LABELS.get(key, key),
            "count": succ,
            "attempts": a["count"],
            "avg_seconds": round(a["total_seconds"] / succ, 1) if succ else 0.0,
        })
    return out


def _saved_minutes(settings: Settings, creations: int, distills: int) -> int:
    per = max(0, settings.dashboard_minutes_write_per_post - settings.dashboard_minutes_ai_draft_per_post)
    return creations * per + distills * settings.dashboard_minutes_research_per_distill


def build_overview(db: Session, settings: Settings, tenant_id: int, range_key: str = "30d") -> dict:
    since = _since(range_key)

    activities = _activity_stats(db, tenant_id, since)
    counts = {a["key"]: a["count"] for a in activities}

    # 创作 / 发布(租户合计)
    pkg_stmt = select(XhsPublishPackage).where(XhsPublishPackage.tenant_id == tenant_id)
    if since is not None:
        pkg_stmt = pkg_stmt.where(XhsPublishPackage.created_at >= since)
    packages = list(db.scalars(pkg_stmt))
    created = len(packages)
    published = sum(1 for p in packages if p.published_at is not None)

    # 对标库规模(不分时间)
    benchmark_count = db.scalar(
        select(func.count()).select_from(BloggerProfile)
        .where(BloggerProfile.tenant_id == tenant_id, BloggerProfile.account_type == "benchmark")
    ) or 0
    my_account_count = db.scalar(
        select(func.count()).select_from(BloggerProfile)
        .where(BloggerProfile.tenant_id == tenant_id, BloggerProfile.account_type == "mine")
    ) or 0
    post_count = db.scalar(
        select(func.count()).select_from(BloggerPost).where(BloggerPost.tenant_id == tenant_id)
    ) or 0

    saved_minutes = _saved_minutes(settings, created, counts.get("blogger_distillation", 0))

    # 最近活动
    recent = list(db.scalars(
        select(OperationTask).where(OperationTask.tenant_id == tenant_id)
        .order_by(OperationTask.created_at.desc()).limit(8)
    ))
    recent_out = [{
        "task_type": t.task_type,
        "label": ACTIVITY_LABELS.get(t.task_type, t.task_type),
        "status": str(getattr(t.status, "value", t.status)),
        "at": t.created_at.isoformat() if t.created_at else None,
    } for t in recent]

    return {
        "range": range_key,
        "activities": activities,
        "creation": {"created": created, "published": published,
                     "conversion": round(published / created, 3) if created else 0.0},
        "library": {"benchmark_count": benchmark_count, "my_account_count": my_account_count, "post_count": post_count},
        "saved_minutes": saved_minutes,
        "recent": recent_out,
    }


def build_account_dashboard(
    db: Session, settings: Settings, tenant_id: int, account_id: int, range_key: str = "30d"
) -> dict:
    account = db.get(BloggerProfile, account_id)
    if not account or account.tenant_id != tenant_id or account.account_type != "mine":
        raise ValueError("账号不存在或不是「我的账号」")
    since = _since(range_key)

    # 为该账号的创作 / 发布
    pkg_stmt = select(XhsPublishPackage).where(
        XhsPublishPackage.tenant_id == tenant_id, XhsPublishPackage.my_account_id == account_id
    )
    if since is not None:
        pkg_stmt = pkg_stmt.where(XhsPublishPackage.created_at >= since)
    packages = list(db.scalars(pkg_stmt))
    created = len(packages)
    published = sum(1 for p in packages if p.published_at is not None)
    saved_minutes = _saved_minutes(settings, created, 0)

    # 该账号笔记的互动：爆款率 + 模态对比(用现有 BloggerPost,blogger_id==account_id)
    posts = list(db.scalars(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == account_id,
            BloggerPost.status == "active",
        )
    ))
    inter = [_interactions(p) for p in posts]
    avg_inter = sum(inter) / len(inter) if inter else 0.0
    threshold = avg_inter * settings.dashboard_viral_multiplier
    viral = sum(1 for v in inter if avg_inter > 0 and v >= threshold)
    by_modality: dict[str, list[int]] = defaultdict(list)
    for p in posts:
        m = "talking_video" if str(getattr(p, "content_subtype", "")) == "talking_video" else "image_text"
        by_modality[m].append(_interactions(p))
    modality = {m: round(sum(v) / len(v), 1) for m, v in by_modality.items() if v}

    return {
        "account": {"id": account.id, "display_name": account.display_name,
                    "follower_count": account.follower_count, "note_total": account.note_total,
                    "platform": account.platform},
        "range": range_key,
        "creation": {"created": created, "published": published,
                     "conversion": round(published / created, 3) if created else 0.0},
        "saved_minutes": saved_minutes,
        "content": {"post_count": len(posts), "avg_interactions": round(avg_inter, 1),
                    "viral_count": viral,
                    "viral_rate": round(viral / len(posts), 3) if posts else 0.0,
                    "by_modality": modality},
    }


def build_account_growth(db: Session, tenant_id: int, account_id: int, range_key: str = "30d") -> dict:
    account = db.get(BloggerProfile, account_id)
    if not account or account.tenant_id != tenant_id or account.account_type != "mine":
        raise ValueError("账号不存在或不是「我的账号」")
    since = _since(range_key)
    since_date = since.date() if since else None

    snap_stmt = select(AccountMetricSnapshot).where(AccountMetricSnapshot.account_id == account_id)
    if since_date is not None:
        snap_stmt = snap_stmt.where(AccountMetricSnapshot.captured_on >= since_date)
    snaps = list(db.scalars(snap_stmt.order_by(AccountMetricSnapshot.captured_on.asc())))
    points = [{"date": s.captured_on.isoformat(), "follower_count": s.follower_count,
               "note_total": s.note_total, "total_interactions": s.total_interactions} for s in snaps]

    # 使用事件打点：租户级的「在用 PubSync」信号(创作/蒸馏) + 本账号已发布
    events: list[dict] = []
    ev_stmt = select(OperationTask).where(
        OperationTask.tenant_id == tenant_id,
        OperationTask.task_type.in_(["xhs_package_draft", "blogger_distillation"]),
    )
    if since is not None:
        ev_stmt = ev_stmt.where(OperationTask.created_at >= since)
    for t in db.scalars(ev_stmt):
        if t.created_at:
            events.append({"date": t.created_at.date().isoformat(),
                           "type": t.task_type, "label": ACTIVITY_LABELS.get(t.task_type, t.task_type)})
    pub_stmt = select(XhsPublishPackage).where(
        XhsPublishPackage.tenant_id == tenant_id, XhsPublishPackage.my_account_id == account_id,
        XhsPublishPackage.published_at.is_not(None),
    )
    for p in db.scalars(pub_stmt):
        if p.published_at and (since is None or p.published_at >= since):
            events.append({"date": p.published_at.date().isoformat(), "type": "published", "label": "发布"})

    comparison = _active_vs_silent(snaps, {date.fromisoformat(e["date"]) for e in events})
    return {"account_id": account_id, "range": range_key, "points": points,
            "events": events, "comparison": comparison,
            "disclaimer": "以上为相关性参考，非因果证明；最终效果取决于内容本身。"}


def _active_vs_silent(snaps: list[AccountMetricSnapshot], active_days: set[date]) -> dict:
    """按 ISO 周分桶：有使用事件的周=活跃周，比较活跃周 vs 沉默周的日均涨粉。数据不足返回 None。"""
    by_week: dict[tuple[int, int], list[AccountMetricSnapshot]] = defaultdict(list)
    for s in snaps:
        iso = s.captured_on.isocalendar()
        by_week[(iso[0], iso[1])].append(s)
    active_weeks: list[float] = []
    silent_weeks: list[float] = []
    for _wk, group in by_week.items():
        group.sort(key=lambda x: x.captured_on)
        if len(group) < 2:
            continue
        days = (group[-1].captured_on - group[0].captured_on).days or 1
        daily = (group[-1].follower_count - group[0].follower_count) / days
        is_active = any(s.captured_on in active_days for s in group)
        (active_weeks if is_active else silent_weeks).append(daily)
    if not active_weeks and not silent_weeks:
        return {"active_avg_daily": None, "silent_avg_daily": None,
                "active_weeks": 0, "silent_weeks": 0}
    return {
        "active_avg_daily": round(sum(active_weeks) / len(active_weeks), 1) if active_weeks else None,
        "silent_avg_daily": round(sum(silent_weeks) / len(silent_weeks), 1) if silent_weeks else None,
        "active_weeks": len(active_weeks), "silent_weeks": len(silent_weeks),
    }


def _interactions_sum(db: Session, tenant_id: int, account_id: int) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(BloggerPost.like_count + BloggerPost.comment_count + BloggerPost.share_count), 0))
        .where(BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == account_id, BloggerPost.status == "active")
    )
    return int(total or 0)


def capture_account_snapshot(db: Session, settings: Settings, account: BloggerProfile, today: date) -> None:
    """给单个「我的账号」拍当日快照(幂等:同日覆盖)。best-effort 刷新最新粉丝/笔记数。"""
    from app.blogger_distillation.service.collection import refresh_blogger_profile

    try:
        refresh_blogger_profile(db, settings, account.tenant_id, account.id)
        db.refresh(account)
    except Exception:  # noqa: BLE001 - 刷新失败就用库里已有的当前值,不影响其它账号
        db.rollback()

    snap = db.scalar(
        select(AccountMetricSnapshot).where(
            AccountMetricSnapshot.account_id == account.id, AccountMetricSnapshot.captured_on == today
        )
    )
    interactions = _interactions_sum(db, account.tenant_id, account.id)
    if snap is None:
        db.add(AccountMetricSnapshot(
            tenant_id=account.tenant_id, account_id=account.id, captured_on=today,
            follower_count=account.follower_count or 0, note_total=account.note_total,
            total_interactions=interactions,
        ))
    else:
        snap.follower_count = account.follower_count or 0
        snap.note_total = account.note_total
        snap.total_interactions = interactions
    db.commit()


def capture_daily_snapshots() -> None:
    """定时任务入口(无参,自建 session):给所有「我的账号」拍当日快照。没有账号则空转。"""
    import logging

    from app.config import get_settings
    from app.database import SessionLocal
    from app.models import Tenant, TenantStatus

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        settings = get_settings()
        today = datetime.now(timezone.utc).date()
        accounts = list(db.scalars(
            select(BloggerProfile)
            .join(Tenant, Tenant.id == BloggerProfile.tenant_id)
            .where(BloggerProfile.account_type == "mine", Tenant.status == TenantStatus.active)
        ))
        for account in accounts:
            try:
                capture_account_snapshot(db, settings, account, today)
            except Exception:  # noqa: BLE001 - 单账号失败不拖垮整批
                db.rollback()
                logger.exception("账号快照失败：account_id=%s", account.id)
        if accounts:
            logger.info("效果看板：完成 %s 个账号当日快照", len(accounts))
    finally:
        db.close()


def mark_package_published(db: Session, tenant_id: int, package_id: int, published: bool) -> XhsPublishPackage:
    pkg = db.get(XhsPublishPackage, package_id)
    if not pkg or pkg.tenant_id != tenant_id:
        raise ValueError("发布包不存在")
    if published:
        pkg.published_at = datetime.now(timezone.utc)
        pkg.status = "published"
    else:
        pkg.published_at = None
        pkg.status = "generated"
    db.commit()
    db.refresh(pkg)
    return pkg
