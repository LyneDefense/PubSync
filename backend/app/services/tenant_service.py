from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentProfile, Tenant, TenantStatus, WeChatAccount


DEFAULT_TENANT_ID = 1


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
            )
        )
    if not db.get(WeChatAccount, tenant.id):
        db.add(WeChatAccount(tenant_id=tenant.id))
    db.commit()


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
