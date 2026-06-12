from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.database import get_db
from app.models import OperationTask, Tenant, XhsPublishPackage
from app.queue import submit_background
from app.schemas import (
    OperationTaskRead,
    XhsPublishPackageCreate,
    XhsPublishPackageDraftRead,
    XhsPublishPackageRead,
    XhsPublishPackageSave,
    XhsTopicIdeaRequest,
    XhsTopicIdeaResponse,
)
from app.services.ai_service import AIServiceError
from app.services.task_service import create_operation_task, run_xhs_package_draft_task
from app.xhs_creation.service import (
    create_xhs_publish_package,
    generate_xhs_publish_package_draft,
    generate_xhs_topic_ideas,
)

router = APIRouter()


@router.get("/xhs/publish-packages", response_model=list[XhsPublishPackageRead])
def list_xhs_publish_packages_endpoint(
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[XhsPublishPackage]:
    stmt = (
        select(XhsPublishPackage)
        .where(XhsPublishPackage.tenant_id == tenant.id)
        .order_by(XhsPublishPackage.created_at.desc(), XhsPublishPackage.id.desc())
    )
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.post("/xhs/publish-packages", response_model=XhsPublishPackageRead)
def create_xhs_publish_package_endpoint(
    payload: XhsPublishPackageSave,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> XhsPublishPackage:
    try:
        return create_xhs_publish_package(db, tenant.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/xhs/package-drafts", response_model=XhsPublishPackageDraftRead)
def generate_xhs_publish_package_draft_endpoint(
    payload: XhsPublishPackageCreate,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return generate_xhs_publish_package_draft(db, settings, tenant.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/xhs/package-drafts/generate", response_model=OperationTaskRead)
def generate_xhs_publish_package_draft_task_endpoint(
    payload: XhsPublishPackageCreate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> OperationTask:
    task = create_operation_task(db, "xhs_package_draft", tenant_id=tenant.id)
    submit_background(background_tasks, run_xhs_package_draft_task, task.id, payload.model_dump())
    return task


@router.post("/xhs/topic-ideas", response_model=XhsTopicIdeaResponse)
def generate_xhs_topic_ideas_endpoint(
    payload: XhsTopicIdeaRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return {"ideas": generate_xhs_topic_ideas(db, settings, tenant.id, payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
