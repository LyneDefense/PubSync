from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import current_username, settings
from app.database import get_db
from app.models import Tenant
from app.schemas import TenantRead
from app.services.auth_service import tenant_ids_for_user
from app.services.tenant_service import list_tenants

router = APIRouter()


@router.get("/tenants", response_model=list[TenantRead])
def list_tenants_endpoint(request: Request, db: Session = Depends(get_db)) -> list[Tenant]:
    username = current_username(request)
    allowed_tenant_ids = tenant_ids_for_user(username, settings, db)
    tenants = [tenant for tenant in list_tenants(db) if tenant.id in allowed_tenant_ids]
    if not tenants:
        raise HTTPException(status_code=403, detail="当前账号没有可访问的工作空间")
    return tenants
