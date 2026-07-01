"""对标库 CRUD:博主增删改查、收藏、刷新主页资料,以及该博主的笔记列表 / Skill 列表。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.blogger_distillation.service import (
    create_blogger,
    delete_blogger,
    exclude_posts,
    refresh_blogger_profile,
    set_blogger_favorite,
    update_blogger,
)
from app.blogger_distillation.tikhub_client import TikHubError
from app.database import get_db
from app.models import BloggerPost, BloggerProfile, BloggerSkill, Tenant
from app.schemas import (
    BloggerFavoriteUpdate,
    BloggerPostRead,
    BloggerPostsDeleteRequest,
    BloggerProfileCreate,
    BloggerProfileRead,
    BloggerProfileUpdate,
    BloggerSkillRead,
)

router = APIRouter()


@router.get("/bloggers", response_model=list[BloggerProfileRead])
def list_bloggers_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    account_type: str | None = Query(default=None, pattern="^(benchmark|mine)$"),
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerProfile]:
    stmt = (
        select(BloggerProfile)
        .where(BloggerProfile.tenant_id == tenant.id, BloggerProfile.platform == platform)
        .order_by(BloggerProfile.is_favorite.desc(), BloggerProfile.updated_at.desc(), BloggerProfile.id.desc())
    )
    if account_type:
        stmt = stmt.where(BloggerProfile.account_type == account_type)
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.post("/bloggers", response_model=BloggerProfileRead)
def create_blogger_endpoint(
    payload: BloggerProfileCreate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    try:
        return create_blogger(
            db,
            tenant.id,
            payload.platform,
            payload.external_id,
            payload.display_name,
            payload.homepage_url,
            payload.avatar_url,
            payload.follower_count,
            payload.niche,
            payload.description,
            account_type=payload.account_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/bloggers/{blogger_id}", response_model=BloggerProfileRead)
def update_blogger_endpoint(
    blogger_id: int,
    payload: BloggerProfileUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    updates = payload.model_dump(exclude_unset=True)
    try:
        return update_blogger(db, tenant.id, blogger_id, **updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bloggers/{blogger_id}/refresh-profile", response_model=BloggerProfileRead)
def refresh_blogger_profile_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    try:
        return refresh_blogger_profile(db, settings, tenant.id, blogger_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TikHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.patch("/bloggers/{blogger_id}/favorite", response_model=BloggerProfileRead)
def update_blogger_favorite_endpoint(
    blogger_id: int,
    payload: BloggerFavoriteUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> BloggerProfile:
    try:
        return set_blogger_favorite(db, tenant.id, blogger_id, payload.is_favorite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/bloggers/{blogger_id}", status_code=204)
def delete_blogger_endpoint(
    blogger_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_blogger(db, tenant.id, blogger_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/bloggers/{blogger_id}/posts", response_model=list[BloggerPostRead])
def list_blogger_posts_endpoint(
    blogger_id: int,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerPost]:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Blogger not found")
    stmt = (
        select(BloggerPost)
        .where(BloggerPost.tenant_id == tenant.id, BloggerPost.blogger_id == blogger_id, BloggerPost.status != "excluded")
        .order_by(BloggerPost.score.desc(), BloggerPost.created_at.desc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.post("/bloggers/{blogger_id}/posts/delete")
def delete_blogger_posts_endpoint(
    blogger_id: int,
    payload: BloggerPostsDeleteRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """软删(排除)博主的若干笔记:单删/批量共用。excluded 后笔记池隐藏、蒸馏/诊断不选、采集不再翻回。"""
    try:
        excluded = exclude_posts(db, tenant.id, blogger_id, payload.post_ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"excluded": excluded}


@router.get("/blogger-skills", response_model=list[BloggerSkillRead])
def list_blogger_skills_endpoint(
    platform: str = Query(default="xhs", pattern="^(xhs|douyin)$"),
    blogger_id: int | None = None,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[BloggerSkill]:
    stmt = (
        select(BloggerSkill)
        .join(BloggerProfile, BloggerProfile.id == BloggerSkill.blogger_id)
        .where(BloggerSkill.tenant_id == tenant.id, BloggerProfile.platform == platform)
        .order_by(BloggerSkill.created_at.desc())
    )
    if blogger_id:
        stmt = stmt.where(BloggerSkill.blogger_id == blogger_id)
    return list(db.scalars(apply_pagination(stmt, limit, offset)))
