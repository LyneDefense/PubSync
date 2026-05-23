import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ContentGroup, ContentProfile, LayoutSettings, PublishingSettings, Tenant, TenantStatus, WeChatAccount
from app.news_fetching.sources import default_source_urls
from app.schemas import (
    ContentGroupUpdate,
    ContentProfileUpdate,
    LayoutSettingsUpdate,
    PublishingSettingsUpdate,
    WeChatAccountUpdate,
)


DEFAULT_TENANT_ID = 1
MAX_CONTENT_GROUPS = 6


def get_default_tenant(db: Session) -> Tenant:
    tenant = db.get(Tenant, DEFAULT_TENANT_ID)
    if tenant:
        ensure_tenant_defaults(db, tenant)
        return tenant

    tenant = Tenant(id=DEFAULT_TENANT_ID, name="AI 科技早报", slug="ai-tech", status=TenantStatus.active)
    db.add(tenant)
    db.flush()
    ensure_tenant_defaults(db, tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def list_tenants(db: Session) -> list[Tenant]:
    tenants = list(db.scalars(select(Tenant).where(Tenant.status == TenantStatus.active).order_by(Tenant.id.asc())))
    if tenants:
        return tenants
    return [get_default_tenant(db)]


def get_tenant(db: Session, tenant_id: int | None) -> Tenant:
    if tenant_id is None:
        return get_default_tenant(db)
    tenant = db.get(Tenant, tenant_id)
    if not tenant or tenant.status != TenantStatus.active:
        raise ValueError("工作空间不存在或已停用")
    ensure_tenant_defaults(db, tenant)
    return tenant


def ensure_tenant_defaults(db: Session, tenant: Tenant) -> None:
    if not db.get(ContentProfile, tenant.id):
        db.add(
            ContentProfile(
                tenant_id=tenant.id,
                publication_name=tenant.name,
                workspace_title="AI 早报" if tenant.id == DEFAULT_TENANT_ID else tenant.name,
                title_prefix="AI科技早报 | " if tenant.id == DEFAULT_TENANT_ID else f"{tenant.name} | ",
                grouping_mode="regional" if tenant.id == DEFAULT_TENANT_ID else "none",
            )
        )
    if not db.get(WeChatAccount, tenant.id):
        db.add(WeChatAccount(tenant_id=tenant.id))
    if not db.get(LayoutSettings, tenant.id):
        db.add(
            LayoutSettings(
                tenant_id=tenant.id,
                template_name="clean" if tenant.id == DEFAULT_TENANT_ID else "warm",
                primary_color="#0f766e" if tenant.id == DEFAULT_TENANT_ID else "#b45309",
                accent_color="#64748b" if tenant.id == DEFAULT_TENANT_ID else "#d97706",
                section_spacing=28 if tenant.id == DEFAULT_TENANT_ID else 24,
                image_radius=8 if tenant.id == DEFAULT_TENANT_ID else 10,
                show_group_heading=tenant.id == DEFAULT_TENANT_ID,
            )
        )
    if not db.get(PublishingSettings, tenant.id):
        db.add(PublishingSettings(tenant_id=tenant.id))
    db.flush()
    ensure_content_group_defaults(db, tenant)
    db.commit()


def ensure_content_group_defaults(db: Session, tenant: Tenant) -> None:
    existing = list_content_groups(db, tenant.id, enabled_only=False)
    if existing:
        return
    if tenant.id == DEFAULT_TENANT_ID:
        defaults = [
            ContentGroup(
                tenant_id=tenant.id,
                group_key="global",
                name="国际动态",
                source_urls=default_source_urls("global"),
                candidate_limit=40,
                article_min=3,
                article_target=6,
                article_max=7,
                position=0,
            ),
            ContentGroup(
                tenant_id=tenant.id,
                group_key="china",
                name="国内动态",
                source_urls=default_source_urls("china"),
                candidate_limit=40,
                article_min=1,
                article_target=3,
                article_max=4,
                position=1,
            ),
        ]
    else:
        defaults = [
            ContentGroup(
                tenant_id=tenant.id,
                group_key="pet-health",
                name="宠物健康",
                source_urls=default_source_urls("pet-health"),
                candidate_limit=30,
                article_min=0,
                article_target=3,
                article_max=4,
                position=0,
            ),
            ContentGroup(
                tenant_id=tenant.id,
                group_key="pet-knowledge",
                name="养宠知识",
                source_urls=default_source_urls("pet-knowledge"),
                candidate_limit=30,
                article_min=0,
                article_target=3,
                article_max=4,
                position=1,
            ),
            ContentGroup(
                tenant_id=tenant.id,
                group_key="pet-industry",
                name="行业资讯",
                source_urls=default_source_urls("pet-industry"),
                candidate_limit=20,
                article_min=0,
                article_target=2,
                article_max=3,
                position=2,
            ),
        ]
    db.add_all(defaults)


def get_profile(db: Session, tenant: Tenant) -> ContentProfile:
    ensure_tenant_defaults(db, tenant)
    profile = db.get(ContentProfile, tenant.id)
    if not profile:
        raise RuntimeError("工作空间内容画像初始化失败")
    return profile


def get_wechat_account(db: Session, tenant: Tenant) -> WeChatAccount:
    ensure_tenant_defaults(db, tenant)
    account = db.get(WeChatAccount, tenant.id)
    if not account:
        raise RuntimeError("工作空间公众号配置初始化失败")
    return account


def get_layout_settings(db: Session, tenant: Tenant) -> LayoutSettings:
    ensure_tenant_defaults(db, tenant)
    layout = db.get(LayoutSettings, tenant.id)
    if not layout:
        raise RuntimeError("工作空间排版配置初始化失败")
    return layout


def get_publishing_settings(db: Session, tenant: Tenant) -> PublishingSettings:
    ensure_tenant_defaults(db, tenant)
    publishing = db.get(PublishingSettings, tenant.id)
    if not publishing:
        raise RuntimeError("工作空间发布配置初始化失败")
    return publishing


def list_content_groups(db: Session, tenant_id: int, enabled_only: bool = False) -> list[ContentGroup]:
    stmt = select(ContentGroup).where(ContentGroup.tenant_id == tenant_id).order_by(ContentGroup.position.asc(), ContentGroup.id.asc())
    if enabled_only:
        stmt = stmt.where(ContentGroup.enabled.is_(True))
    return list(db.scalars(stmt))


def get_content_groups(db: Session, tenant: Tenant, enabled_only: bool = False) -> list[ContentGroup]:
    ensure_tenant_defaults(db, tenant)
    return list_content_groups(db, tenant.id, enabled_only=enabled_only)


def update_profile(db: Session, tenant: Tenant, payload: ContentProfileUpdate) -> ContentProfile:
    profile = get_profile(db, tenant)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(profile, key, value)
    if data.get("publication_name"):
        tenant.name = str(data["publication_name"]).strip()
    db.commit()
    db.refresh(profile)
    return profile


def update_wechat_account(db: Session, tenant: Tenant, payload: WeChatAccountUpdate) -> WeChatAccount:
    account = get_wechat_account(db, tenant)
    data = payload.model_dump(exclude_unset=True)
    if "app_id" in data and data["app_id"] is not None:
        account.app_id = data["app_id"].strip()
    if "app_secret" in data and data["app_secret"]:
        account.app_secret = data["app_secret"].strip()
    db.commit()
    db.refresh(account)
    return account


def update_layout_settings(db: Session, tenant: Tenant, payload: LayoutSettingsUpdate) -> LayoutSettings:
    layout = get_layout_settings(db, tenant)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(layout, key, value)
    db.commit()
    db.refresh(layout)
    return layout


def update_publishing_settings(db: Session, tenant: Tenant, payload: PublishingSettingsUpdate) -> PublishingSettings:
    publishing = get_publishing_settings(db, tenant)
    data = payload.model_dump(exclude_unset=True)
    if "max_article_images" in data and "min_article_images" in data:
        data["min_article_images"] = min(data["min_article_images"], data["max_article_images"])
    for key, value in data.items():
        if value is not None:
            setattr(publishing, key, normalize_publishing_value(key, value))
    if publishing.min_article_images > publishing.max_article_images:
        publishing.min_article_images = publishing.max_article_images
    db.commit()
    db.refresh(publishing)
    return publishing


def update_content_groups(db: Session, tenant: Tenant, payload: list[ContentGroupUpdate]) -> list[ContentGroup]:
    normalized = normalize_group_payload(payload)
    db.execute(delete(ContentGroup).where(ContentGroup.tenant_id == tenant.id))
    for position, item in enumerate(normalized):
        db.add(
            ContentGroup(
                tenant_id=tenant.id,
                group_key=item["group_key"],
                name=item["name"],
                source_urls=item["source_urls"],
                candidate_limit=item["candidate_limit"],
                article_min=item["article_min"],
                article_target=item["article_target"],
                article_max=item["article_max"],
                position=position,
                enabled=item["enabled"],
            )
        )
    db.commit()
    return list_content_groups(db, tenant.id, enabled_only=False)


def normalize_group_payload(payload: list[ContentGroupUpdate]) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    used_keys: set[str] = set()
    for index, item in enumerate(payload[:MAX_CONTENT_GROUPS]):
        data = item.model_dump(exclude_unset=True)
        raw_name = str(data.get("name") or "").strip()
        if not raw_name:
            continue
        group_key = normalize_group_key(data.get("group_key") or raw_name or f"group-{index + 1}")
        while group_key in used_keys:
            group_key = f"{group_key}-{index + 1}"
        used_keys.add(group_key)
        article_max = clamp_int(data.get("article_max"), 0, 50, 8)
        article_target = min(clamp_int(data.get("article_target"), 0, 50, min(5, article_max)), article_max)
        article_min = min(clamp_int(data.get("article_min"), 0, 50, 0), article_target)
        groups.append(
            {
                "group_key": group_key,
                "name": raw_name[:120],
                "source_urls": str(data.get("source_urls") or "").strip(),
                "candidate_limit": clamp_int(data.get("candidate_limit"), 0, 300, 40),
                "article_min": article_min,
                "article_target": article_target,
                "article_max": article_max,
                "enabled": bool(data.get("enabled", True)),
            }
        )
    if not groups:
        groups.append(
            {
                "group_key": "main",
                "name": "精选内容",
                "source_urls": "",
                "candidate_limit": 60,
                "article_min": 0,
                "article_target": 8,
                "article_max": 8,
                "enabled": True,
            }
        )
    return groups


def normalize_group_key(value: object) -> str:
    key = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower()).strip("-_")
    return key[:80] or "main"


def clamp_int(value: object, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_publishing_value(key: str, value: object) -> object:
    if key in {"dedup_direct_similarity", "dedup_review_similarity"}:
        try:
            parsed = float(str(value))
        except (TypeError, ValueError):
            parsed = 0.0
        return str(max(0.0, min(1.0, parsed)))
    return value


class EffectiveSettings:
    def __init__(self, settings: Settings, publishing: PublishingSettings) -> None:
        self._settings = settings
        self._publishing = publishing

    def __getattr__(self, name: str) -> object:
        if hasattr(self._publishing, name):
            value = getattr(self._publishing, name)
            if name in {"dedup_direct_similarity", "dedup_review_similarity"}:
                return float(value)
            return value
        return getattr(self._settings, name)


def build_effective_settings(settings: Settings, publishing: PublishingSettings) -> EffectiveSettings:
    return EffectiveSettings(settings, publishing)
