from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant
from app.database import get_db
from app.models import ContentProfile, Tenant, WeChatAccount
from app.schemas import (
    ContentProfileRead,
    WeChatAccountRead,
    WorkspaceConfigRead,
    WorkspaceConfigUpdate,
)
from app.services.tenant_service import (
    get_content_groups,
    get_layout_settings,
    get_profile,
    get_publishing_settings,
    get_wechat_account,
    update_content_groups,
    update_layout_settings,
    update_profile,
    update_publishing_settings,
    update_wechat_account,
)

router = APIRouter()


def read_wechat_account(account: WeChatAccount) -> WeChatAccountRead:
    return WeChatAccountRead(
        tenant_id=account.tenant_id,
        app_id=account.app_id,
        app_secret_configured=bool(account.app_secret),
    )


@router.get("/profile", response_model=ContentProfileRead)
def get_profile_endpoint(tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)) -> ContentProfile:
    return get_profile(db, tenant)


@router.get("/workspace/config", response_model=WorkspaceConfigRead)
def get_workspace_config_endpoint(
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> WorkspaceConfigRead:
    return WorkspaceConfigRead(
        profile=get_profile(db, tenant),
        wechat=read_wechat_account(get_wechat_account(db, tenant)),
        layout=get_layout_settings(db, tenant),
        publishing=get_publishing_settings(db, tenant),
        content_groups=get_content_groups(db, tenant),
    )


@router.put("/workspace/config", response_model=WorkspaceConfigRead)
def update_workspace_config_endpoint(
    payload: WorkspaceConfigUpdate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> WorkspaceConfigRead:
    profile = get_profile(db, tenant)
    account = get_wechat_account(db, tenant)
    layout = get_layout_settings(db, tenant)
    publishing = get_publishing_settings(db, tenant)
    content_groups = get_content_groups(db, tenant)
    if payload.profile:
        profile = update_profile(db, tenant, payload.profile)
    if payload.wechat:
        account = update_wechat_account(db, tenant, payload.wechat)
    if payload.layout:
        layout = update_layout_settings(db, tenant, payload.layout)
    if payload.publishing:
        publishing = update_publishing_settings(db, tenant, payload.publishing)
    if payload.content_groups is not None:
        content_groups = update_content_groups(db, tenant, payload.content_groups)
    return WorkspaceConfigRead(
        profile=profile,
        wechat=read_wechat_account(account),
        layout=layout,
        publishing=publishing,
        content_groups=content_groups,
    )
