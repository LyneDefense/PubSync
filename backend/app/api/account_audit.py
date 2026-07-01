from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, current_tenant, settings
from app.appraisal.intent import suggest_intent
from app.database import get_db
from app.models import AccountAuditRun, BloggerPost, BloggerProfile, Tenant
from app.queue import submit_background
from app.schemas import (
    AccountAuditCreate,
    AccountAuditRunRead,
    AppraisalIntentContextRequest,
    AppraisalIntentContextResult,
    AppraisalIntentQuestion,
    AppraisalIntentSuggestRequest,
    AppraisalIntentSuggestResult,
    AppraiseCreate,
    OperationTaskRead,
    SelfDiagnoseCreate,
)
from app.services.task_service import create_operation_task, run_account_audit_task, run_appraisal_task

router = APIRouter()


def _require_account(db: Session, tenant_id: int, platform: str, blogger_id: int, label: str) -> BloggerProfile:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"{label}不存在")
    if blogger.platform != platform:
        raise HTTPException(status_code=400, detail=f"{label}与所选平台不一致")
    return blogger


def _recent_titles(db: Session, tenant_id: int, blogger_id: int, limit: int = 30) -> list[str]:
    """意图引导用到的「近期标题」:未下架、按发布时间倒序取前 N 条,去空。"""
    rows = db.scalars(
        select(BloggerPost.title)
        .where(BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger_id,
               BloggerPost.status.notin_(("delisted", "excluded")))
        .order_by(BloggerPost.published_at.desc().nullslast(), BloggerPost.id.desc())
        .limit(limit)
    )
    return [t for t in rows if t]


@router.post("/account-audit", response_model=OperationTaskRead)
def start_account_audit_endpoint(
    payload: AccountAuditCreate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    _require_account(db, tenant.id, payload.platform, payload.my_blogger_id, "我的账号")
    _require_account(db, tenant.id, payload.platform, payload.benchmark_blogger_id, "对标账号")
    task = create_operation_task(db, "account_audit", tenant_id=tenant.id)
    submit_background(background_tasks, run_account_audit_task, task.id, {"kind": "benchmark", **payload.model_dump()})
    return task


@router.post("/account-audit/self", response_model=OperationTaskRead)
def start_self_diagnose_endpoint(
    payload: SelfDiagnoseCreate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    _require_account(db, tenant.id, payload.platform, payload.my_blogger_id, "我的账号")
    task = create_operation_task(db, "account_audit", tenant_id=tenant.id)
    submit_background(background_tasks, run_account_audit_task, task.id, {"kind": "self", **payload.model_dump()})
    return task


@router.post("/account-audit/appraise", response_model=OperationTaskRead)
def start_appraisal_endpoint(
    payload: AppraiseCreate,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    """博主诊断(对标分析):诊断一个号(对标库博主或我的账号)→ 硬/软/合规 三区报告。

    诊断前自动确保 ≥N 条笔记(不够补采);结果落 AccountAuditRun,用 /account-audit/runs 读取。
    """
    blogger = db.get(BloggerProfile, payload.blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="账号不存在")
    task = create_operation_task(db, "account_audit", tenant_id=tenant.id)
    submit_background(background_tasks, run_appraisal_task, task.id, payload.model_dump())
    return task


@router.post("/account-audit/intent-context", response_model=AppraisalIntentContextResult)
def intent_context_endpoint(
    payload: AppraisalIntentContextRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> AppraisalIntentContextResult:
    """答题打卡·「读取 TA 最近笔记」的真实事件:只做便宜的 DB 读,返回将喂给模型的近期笔记数。

    前端答题打卡进度卡的第一段「读取 TA 最近 N 篇笔记」由这个真实返回点亮(N 为真实值),
    再发起 /intent-suggest(模型出题)点亮后两段——两次真实往返,不用前端假装分阶段。
    """
    blogger = db.get(BloggerProfile, payload.blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="账号不存在")
    titles = _recent_titles(db, tenant.id, blogger.id)
    tags = [t for t in (str(x.get("name") or "").strip() for x in blogger.tags) if t]
    has_material = bool(titles or tags or (blogger.niche or "").strip())
    return AppraisalIntentContextResult(note_count=len(titles), has_material=has_material)


@router.post("/account-audit/intent-suggest", response_model=AppraisalIntentSuggestResult)
def suggest_appraisal_intent_endpoint(
    payload: AppraisalIntentSuggestRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> AppraisalIntentSuggestResult:
    """对标分析·意图引导(同步):看选中博主在做什么 → 判断意图够不够具体 → 不够给几个多选题帮用户明确。"""
    blogger = db.get(BloggerProfile, payload.blogger_id)
    if not blogger or blogger.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="账号不存在")
    titles = _recent_titles(db, tenant.id, blogger.id)
    tags = [str(t.get("name") or "") for t in blogger.tags]
    result = suggest_intent(
        settings,
        titles=titles,
        tags=tags,
        niche=blogger.niche or "",
        intent=payload.intent,
        purpose=payload.kind,
        timeout=settings.appraisal_llm_timeout,
    )
    return AppraisalIntentSuggestResult(
        clear=bool(result["clear"]),
        questions=[
            AppraisalIntentQuestion(
                q=q["q"],
                options=q["options"],
                multi=bool(q.get("multi", True)),
                allow_other=bool(q.get("allow_other", True)),
            )
            for q in result["questions"]
        ],
    )


@router.get("/account-audit/runs", response_model=list[AccountAuditRunRead])
def list_account_audit_runs_endpoint(
    platform: str | None = None,
    kind: str | None = None,
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> list[AccountAuditRun]:
    stmt = select(AccountAuditRun).where(AccountAuditRun.tenant_id == tenant.id)
    if platform:
        stmt = stmt.where(AccountAuditRun.platform == platform)
    if kind:
        stmt = stmt.where(AccountAuditRun.kind == kind)
    stmt = stmt.order_by(AccountAuditRun.created_at.desc(), AccountAuditRun.id.desc())
    return list(db.scalars(apply_pagination(stmt, limit, offset)))


@router.get("/account-audit/runs/{run_id}", response_model=AccountAuditRunRead)
def get_account_audit_run_endpoint(
    run_id: int,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
) -> AccountAuditRun:
    run = db.get(AccountAuditRun, run_id)
    if not run or run.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="账号体检记录不存在")
    return run
