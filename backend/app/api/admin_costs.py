"""后台费用记录 API:明细列表、汇总(分渠道/按工作空间)、模型单价读写。均需管理员。"""

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import LimitQuery, OffsetQuery, apply_pagination, require_admin
from app.cost.pricing import CONFIG_KEY, load_prices
from app.database import get_db
from app.models import CostEvent, SystemConfig, Tenant
from app.models.common import utc_now
from app.schemas import CostByKey, CostEventRead, CostSummary, ModelPrices

router = APIRouter()

PROVIDER_LABELS = {"tikhub": "TikHub", "openai": "OpenAI", "minimax": "MiniMax"}


@router.get("/admin/costs", response_model=list[CostEventRead])
def admin_list_costs_endpoint(
    provider: str | None = Query(default=None),
    tenant_id: int | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=365),
    limit: int | None = LimitQuery,
    offset: int = OffsetQuery,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[CostEventRead]:
    stmt = select(CostEvent, Tenant.name).join(Tenant, Tenant.id == CostEvent.tenant_id, isouter=True)
    if provider:
        stmt = stmt.where(CostEvent.provider == provider)
    if tenant_id:
        stmt = stmt.where(CostEvent.tenant_id == tenant_id)
    if days:
        stmt = stmt.where(CostEvent.created_at >= utc_now() - timedelta(days=days))
    stmt = stmt.order_by(CostEvent.created_at.desc(), CostEvent.id.desc())
    rows = db.execute(apply_pagination(stmt, limit if limit is not None else 100, offset)).all()
    return [
        CostEventRead(
            id=ev.id,
            created_at=ev.created_at,
            tenant_id=ev.tenant_id,
            tenant_name=tenant_name,
            task_id=ev.task_id,
            provider=ev.provider,
            kind=ev.kind,
            model=ev.model,
            quantity=ev.quantity,
            unit=ev.unit,
            cost_usd=ev.cost_usd,
            meta_json=ev.meta_json,
        )
        for ev, tenant_name in rows
    ]


@router.get("/admin/costs/summary", response_model=CostSummary)
def admin_cost_summary_endpoint(
    days: int = Query(default=30, ge=1, le=365),
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CostSummary:
    since = utc_now() - timedelta(days=days)
    base = select(CostEvent).where(CostEvent.created_at >= since).subquery()

    total = db.execute(select(func.coalesce(func.sum(base.c.cost_usd), 0.0), func.count())).one()

    by_provider_rows = db.execute(
        select(base.c.provider, func.sum(base.c.cost_usd), func.count())
        .group_by(base.c.provider)
        .order_by(func.sum(base.c.cost_usd).desc())
    ).all()
    by_provider = [
        CostByKey(key=p, label=PROVIDER_LABELS.get(p, p), cost_usd=round(c or 0.0, 6), count=n)
        for p, c, n in by_provider_rows
    ]

    by_tenant_rows = db.execute(
        select(base.c.tenant_id, Tenant.name, func.sum(base.c.cost_usd), func.count())
        .join(Tenant, Tenant.id == base.c.tenant_id, isouter=True)
        .group_by(base.c.tenant_id, Tenant.name)
        .order_by(func.sum(base.c.cost_usd).desc())
    ).all()
    by_tenant = [
        CostByKey(
            key=str(tid) if tid is not None else "-",
            label=name or ("未归属" if tid is None else f"工作空间#{tid}"),
            cost_usd=round(c or 0.0, 6),
            count=n,
        )
        for tid, name, c, n in by_tenant_rows
    ]

    return CostSummary(
        days=days,
        total_usd=round(total[0] or 0.0, 6),
        event_count=total[1] or 0,
        by_provider=by_provider,
        by_tenant=by_tenant,
    )


@router.get("/admin/costs/prices", response_model=ModelPrices)
def admin_get_prices_endpoint(_: str = Depends(require_admin), db: Session = Depends(get_db)) -> ModelPrices:
    prices = load_prices(db)
    return ModelPrices(text=prices.get("text", {}), image=prices.get("image", {}))


@router.put("/admin/costs/prices", response_model=ModelPrices)
def admin_put_prices_endpoint(
    payload: ModelPrices,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ModelPrices:
    value = json.dumps({"text": payload.text, "image": payload.image}, ensure_ascii=False)
    db.merge(SystemConfig(key=CONFIG_KEY, value=value, is_secret=False))
    db.commit()
    prices = load_prices(db)
    return ModelPrices(text=prices.get("text", {}), image=prices.get("image", {}))
