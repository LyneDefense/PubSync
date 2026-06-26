"""Skill 优化(训练):发起优化任务(异步)+ 训练记录查询 / 确认采纳。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant
from app.database import get_db
from app.models import BloggerProfile, BloggerSkill, SkillTrainingRun, Tenant
from app.queue import submit_background
from app.schemas import OperationTaskRead
from app.schemas.skill_training import SkillOptimizeConfirm, SkillOptimizeRequest, SkillTrainingRunRead
from app.services.task_service import create_operation_task, run_skill_optimization_task
from app.skill_optimization.service import confirm_skill_optimization

router = APIRouter()


@router.post("/bloggers/{blogger_id}/optimize-skill", response_model=OperationTaskRead)
def optimize_skill_endpoint(
    blogger_id: int,
    payload: SkillOptimizeRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="博主不存在")
    if payload.skill_id is not None:
        chosen = db.get(BloggerSkill, payload.skill_id)
        if not chosen or chosen.tenant_id != tenant.id or chosen.blogger_id != blogger_id:
            raise HTTPException(status_code=400, detail="指定的 Skill 不存在或不属于该博主")
    else:
        has_skill = db.scalar(
            select(BloggerSkill).where(BloggerSkill.blogger_id == blogger_id, BloggerSkill.status == "active")
        )
        if not has_skill:
            raise HTTPException(status_code=400, detail="该博主还没有 active Skill,请先去蒸馏")
    task = create_operation_task(db, "skill_optimization", tenant_id=tenant.id)
    submit_background(
        background_tasks, run_skill_optimization_task, task.id,
        {"blogger_id": blogger_id, "epochs": payload.epochs, "skill_id": payload.skill_id},
    )
    return task


@router.get("/skill-training/runs", response_model=list[SkillTrainingRunRead])
def list_skill_training_runs_endpoint(
    blogger_id: int | None = None,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[SkillTrainingRun]:
    stmt = select(SkillTrainingRun).where(SkillTrainingRun.tenant_id == tenant.id)
    if blogger_id:
        stmt = stmt.where(SkillTrainingRun.blogger_id == blogger_id)
    stmt = stmt.order_by(SkillTrainingRun.created_at.desc(), SkillTrainingRun.id.desc())
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/skill-training/runs/{run_id}", response_model=SkillTrainingRunRead)
def get_skill_training_run_endpoint(
    run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> SkillTrainingRun:
    run = db.get(SkillTrainingRun, run_id)
    if not run or run.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="优化记录不存在")
    return run


@router.post("/skill-training/runs/{run_id}/confirm", response_model=SkillTrainingRunRead)
def confirm_skill_training_run_endpoint(
    run_id: int,
    payload: SkillOptimizeConfirm,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> SkillTrainingRun:
    try:
        return confirm_skill_optimization(db, tenant.id, run_id, payload.adopt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
