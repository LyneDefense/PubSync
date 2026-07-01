from __future__ import annotations

import json

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.blogger_distillation.providers import validate_platform
from app.models import (
    AccountAuditRun,
    AccountMetricSnapshot,
    BenchmarkDiscoverySession,
    BenchmarkRecommendationRun,
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
    BloggerSnapshot,
    OperationTask,
    OperationTaskEvent,
    SkillTrainingRun,
    XhsPublishPackage,
)

_UNSET = object()


def list_snapshots(db: Session, tenant_id: int, blogger_id: int) -> list[BloggerSnapshot]:
    return list(
        db.scalars(
            select(BloggerSnapshot)
            .where(BloggerSnapshot.tenant_id == tenant_id, BloggerSnapshot.blogger_id == blogger_id)
            .order_by(BloggerSnapshot.created_at.desc(), BloggerSnapshot.id.desc())
        )
    )


def create_snapshot(db: Session, tenant_id: int, blogger_id: int, name: str, post_ids: list[int]) -> BloggerSnapshot:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    clean_ids = [int(x) for x in (post_ids or [])]
    if not clean_ids:
        raise ValueError("快照至少要包含一篇笔记")
    snapshot = BloggerSnapshot(
        tenant_id=tenant_id,
        blogger_id=blogger_id,
        name=(name or "").strip() or "未命名快照",
        post_ids_json=json.dumps(clean_ids, ensure_ascii=False),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def update_snapshot(
    db: Session,
    tenant_id: int,
    snapshot_id: int,
    *,
    name: str | None = None,
    post_ids: list[int] | None = None,
) -> BloggerSnapshot:
    """改名 / 重选笔记。name、post_ids 可单独或一起传(None 表示不动该字段)。"""
    snapshot = db.get(BloggerSnapshot, snapshot_id)
    if not snapshot or snapshot.tenant_id != tenant_id:
        raise ValueError("快照不存在或不属于当前工作空间")
    if name is not None:
        clean = name.strip()
        if not clean:
            raise ValueError("快照名称不能为空")
        snapshot.name = clean
    if post_ids is not None:
        clean_ids = [int(x) for x in post_ids]
        if not clean_ids:
            raise ValueError("快照至少要包含一篇笔记")
        snapshot.post_ids_json = json.dumps(clean_ids, ensure_ascii=False)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_snapshot(db: Session, tenant_id: int, snapshot_id: int) -> None:
    snapshot = db.get(BloggerSnapshot, snapshot_id)
    if not snapshot or snapshot.tenant_id != tenant_id:
        raise ValueError("快照不存在或不属于当前工作空间")
    db.delete(snapshot)
    db.commit()


def archive_active_skills(db: Session, tenant_id: int, blogger_id: int) -> None:
    active_skills = db.scalars(
        select(BloggerSkill).where(
            BloggerSkill.tenant_id == tenant_id,
            BloggerSkill.blogger_id == blogger_id,
            BloggerSkill.status == "active",
        )
    )
    for skill in active_skills:
        skill.status = "archived"


def create_blogger(
    db: Session,
    tenant_id: int,
    platform: str,
    external_id: str | None,
    display_name: str,
    homepage_url: str,
    avatar_url: str,
    follower_count: int,
    niche: str,
    description: str,
    account_type: str = "benchmark",
) -> BloggerProfile:
    platform = validate_platform(platform)
    account_type = "mine" if str(account_type).strip().lower() == "mine" else "benchmark"
    clean_external_id = (external_id or "").strip() or None
    existing = None
    if clean_external_id:
        existing = db.scalar(
            select(BloggerProfile).where(
                BloggerProfile.tenant_id == tenant_id,
                BloggerProfile.platform == platform,
                BloggerProfile.external_id == clean_external_id,
            )
        )
    existing = existing or db.scalar(
        select(BloggerProfile).where(BloggerProfile.tenant_id == tenant_id, BloggerProfile.homepage_url == homepage_url)
    )
    if existing:
        existing.platform = platform
        existing.account_type = account_type
        existing.external_id = clean_external_id or existing.external_id
        existing.display_name = display_name
        existing.niche = niche
        existing.avatar_url = avatar_url
        existing.follower_count = max(follower_count, 0)
        existing.description = description
        db.commit()
        db.refresh(existing)
        return existing
    blogger = BloggerProfile(
        tenant_id=tenant_id,
        platform=platform,
        account_type=account_type,
        external_id=clean_external_id,
        display_name=display_name,
        homepage_url=homepage_url,
        avatar_url=avatar_url,
        follower_count=max(follower_count, 0),
        niche=niche,
        description=description,
    )
    db.add(blogger)
    db.commit()
    db.refresh(blogger)
    return blogger


def update_blogger(
    db: Session,
    tenant_id: int,
    blogger_id: int,
    *,
    external_id: str | None | object = _UNSET,
    display_name: str | None = None,
    homepage_url: str | None = None,
    avatar_url: str | None = None,
    follower_count: int | None = None,
    niche: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> BloggerProfile:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    if homepage_url is not None:
        clean_homepage_url = homepage_url.strip()
        if not clean_homepage_url:
            raise ValueError("博主主页链接不能为空")
        existing = db.scalar(
            select(BloggerProfile).where(
                BloggerProfile.tenant_id == tenant_id,
                BloggerProfile.homepage_url == clean_homepage_url,
                BloggerProfile.id != blogger_id,
            )
        )
        if existing:
            raise ValueError("该主页链接已绑定其他博主")
        blogger.homepage_url = clean_homepage_url
    if external_id is not _UNSET:
        clean_external_id = None if external_id is None else str(external_id).strip() or None
        if clean_external_id:
            existing = db.scalar(
                select(BloggerProfile).where(
                    BloggerProfile.tenant_id == tenant_id,
                    BloggerProfile.platform == blogger.platform,
                    BloggerProfile.external_id == clean_external_id,
                    BloggerProfile.id != blogger_id,
                )
            )
            if existing:
                raise ValueError("该平台 ID 已绑定其他博主")
        blogger.external_id = clean_external_id
    if display_name is not None:
        clean_display_name = display_name.strip()
        if not clean_display_name:
            raise ValueError("博主名称不能为空")
        blogger.display_name = clean_display_name
    if avatar_url is not None:
        blogger.avatar_url = avatar_url.strip()
    if follower_count is not None:
        blogger.follower_count = max(follower_count, 0)
    if niche is not None:
        blogger.niche = niche.strip()
    if description is not None:
        blogger.description = description
    if tags is not None:
        from app.blogger_distillation.service.tagging import set_manual_tags

        blogger.tags_json = set_manual_tags(blogger.tags_json, tags)
    db.commit()
    db.refresh(blogger)
    return blogger


def set_blogger_favorite(db: Session, tenant_id: int, blogger_id: int, is_favorite: bool) -> BloggerProfile:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    blogger.is_favorite = is_favorite
    db.commit()
    db.refresh(blogger)
    return blogger


def delete_blogger(db: Session, tenant_id: int, blogger_id: int) -> None:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")

    task_ids = [
        task_id
        for task_id in db.scalars(
            select(BloggerCollectionRun.task_id).where(
                BloggerCollectionRun.tenant_id == tenant_id,
                BloggerCollectionRun.blogger_id == blogger_id,
                BloggerCollectionRun.task_id.is_not(None),
            )
        )
    ]
    task_ids.extend(
        task_id
        for task_id in db.scalars(
            select(BloggerDistillationRun.task_id).where(
                BloggerDistillationRun.tenant_id == tenant_id,
                BloggerDistillationRun.blogger_id == blogger_id,
                BloggerDistillationRun.task_id.is_not(None),
            )
        )
    )

    # 先清所有外键指向该博主的子表,否则 db.delete(blogger) 会撞 FK 约束(整删失败、报 500)。
    # blogger 已按 tenant 校验(上方),子表按博主外键删即可(不会跨租户)。
    db.execute(delete(XhsPublishPackage).where(or_(XhsPublishPackage.blogger_id == blogger_id, XhsPublishPackage.my_account_id == blogger_id)))
    db.execute(delete(BloggerSkill).where(BloggerSkill.blogger_id == blogger_id))
    db.execute(delete(SkillTrainingRun).where(SkillTrainingRun.blogger_id == blogger_id))
    db.execute(delete(BloggerCollectionPost).where(BloggerCollectionPost.blogger_id == blogger_id))
    db.execute(delete(BloggerDistillationRun).where(BloggerDistillationRun.blogger_id == blogger_id))
    db.execute(delete(BloggerCollectionRun).where(BloggerCollectionRun.blogger_id == blogger_id))
    db.execute(delete(BloggerSnapshot).where(BloggerSnapshot.blogger_id == blogger_id))
    db.execute(delete(AccountMetricSnapshot).where(AccountMetricSnapshot.account_id == blogger_id))
    db.execute(delete(BenchmarkRecommendationRun).where(BenchmarkRecommendationRun.my_account_id == blogger_id))
    db.execute(delete(BenchmarkDiscoverySession).where(BenchmarkDiscoverySession.my_account_id == blogger_id))
    db.execute(delete(AccountAuditRun).where(or_(AccountAuditRun.my_blogger_id == blogger_id, AccountAuditRun.benchmark_blogger_id == blogger_id)))
    db.execute(delete(BloggerPost).where(BloggerPost.blogger_id == blogger_id))
    db.delete(blogger)
    if task_ids:
        db.execute(delete(OperationTaskEvent).where(OperationTaskEvent.tenant_id == tenant_id, OperationTaskEvent.task_id.in_(task_ids)))
        db.execute(delete(OperationTask).where(OperationTask.tenant_id == tenant_id, OperationTask.id.in_(task_ids)))
    db.commit()


def exclude_posts(db: Session, tenant_id: int, blogger_id: int, post_ids: list[int]) -> int:
    """软删(排除)博主的若干笔记:标 status='excluded' —— 笔记池隐藏、蒸馏/诊断不选、采集不再翻回。

    同步递减博主 sample_count、从快照 post_ids 里剔除(快照本身保留)。返回实际排除的条数。
    软删而非硬删:保留历史、可回溯,且采集侧靠 status 判断不再重复采回。
    """
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    clean_ids = {int(x) for x in (post_ids or [])}
    if not clean_ids:
        raise ValueError("请至少选择一篇笔记")
    posts = list(
        db.scalars(
            select(BloggerPost).where(
                BloggerPost.tenant_id == tenant_id,
                BloggerPost.blogger_id == blogger_id,
                BloggerPost.id.in_(clean_ids),
                BloggerPost.status != "excluded",
            )
        )
    )
    if not posts:
        return 0
    excluded_ids: set[int] = set()
    for post in posts:
        post.status = "excluded"
        excluded_ids.add(post.id)
    blogger.sample_count = max(0, (blogger.sample_count or 0) - len(excluded_ids))
    snapshots = db.scalars(
        select(BloggerSnapshot).where(
            BloggerSnapshot.tenant_id == tenant_id,
            BloggerSnapshot.blogger_id == blogger_id,
        )
    )
    for snap in snapshots:
        try:
            ids = json.loads(snap.post_ids_json or "[]")
        except json.JSONDecodeError:
            ids = []
        kept = [i for i in ids if int(i) not in excluded_ids]
        if len(kept) != len(ids):
            snap.post_ids_json = json.dumps(kept, ensure_ascii=False)
    db.commit()
    return len(excluded_ids)
