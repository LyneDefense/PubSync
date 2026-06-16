"""费用捕获上下文。

用 contextvar 记录"当前在为哪个 tenant/task 计费",并缓冲本次任务内发生的费用事件,任务结束统一
落库。这样 ai_service / tikhub 等深处的 chokepoint 无需层层透传 db/tenant/task,只调一个 record_*。
无上下文时(非任务场景)兜底直接写一条,保证不漏记。
"""

from __future__ import annotations

import contextvars
import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from app.cost.pricing import load_prices, price_image, price_text
from app.database import SessionLocal
from app.models import CostEvent

logger = logging.getLogger(__name__)


@dataclass
class _CostCtx:
    tenant_id: int | None
    task_id: str | None
    prices: dict[str, Any]
    buffer: list[dict[str, Any]] = field(default_factory=list)


_cost_ctx: contextvars.ContextVar[_CostCtx | None] = contextvars.ContextVar("cost_ctx", default=None)


def _standalone_prices() -> dict[str, Any]:
    db = SessionLocal()
    try:
        return load_prices(db)
    finally:
        db.close()


def _current_prices() -> dict[str, Any]:
    ctx = _cost_ctx.get()
    return ctx.prices if ctx else _standalone_prices()


def add_cost(
    *,
    provider: str,
    kind: str,
    cost_usd: float,
    quantity: int = 0,
    unit: str = "request",
    model: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """登记一条费用事件:有上下文则入缓冲,否则兜底直接写库。"""
    event = {
        "provider": provider,
        "kind": kind,
        "model": model,
        "quantity": int(quantity),
        "unit": unit,
        "cost_usd": float(cost_usd),
        "meta_json": json.dumps(meta, ensure_ascii=False) if meta else None,
    }
    ctx = _cost_ctx.get()
    if ctx is not None:
        ctx.buffer.append(event)
        return
    db = SessionLocal()
    try:
        db.add(CostEvent(tenant_id=None, task_id=None, **event))
        db.commit()
    except Exception:  # noqa: BLE001 - 记账失败不应影响主流程
        db.rollback()
        logger.exception("写入费用事件失败(无上下文兜底)")
    finally:
        db.close()


def record_text_usage(provider: str, model: str | None, data: dict[str, Any]) -> None:
    """从 LLM 响应里取 token 用量并按单价折算记账。token 缺失时按 0,不报错。"""
    try:
        usage = data.get("usage") if isinstance(data, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        if not prompt and not completion:
            total = int(usage.get("total_tokens") or 0)
            completion = total
        cost = price_text(_current_prices(), model, prompt, completion)
        add_cost(
            provider=provider,
            kind="text",
            model=model,
            quantity=prompt + completion,
            unit="token",
            cost_usd=cost,
            meta={"prompt_tokens": prompt, "completion_tokens": completion},
        )
    except Exception:  # noqa: BLE001 - 记账失败不应影响生成
        logger.exception("记录 LLM 文本费用失败")


def record_image_usage(provider: str, model: str | None, n: int = 1) -> None:
    try:
        cost = price_image(_current_prices(), model, n)
        add_cost(provider=provider, kind="image", model=model, quantity=n, unit="image", cost_usd=cost)
    except Exception:  # noqa: BLE001
        logger.exception("记录 LLM 图像费用失败")


def record_tikhub(kind: str, requests: int, cost_usd: float) -> None:
    add_cost(provider="tikhub", kind=kind, model=None, quantity=requests, unit="request", cost_usd=cost_usd)


@contextmanager
def cost_capture(tenant_id: int | None, task_id: str | None):
    """包裹一个任务:进入时载入单价,期间所有 record_* 缓冲,退出时统一落库。"""
    ctx = _CostCtx(tenant_id=tenant_id, task_id=task_id, prices=_standalone_prices())
    token = _cost_ctx.set(ctx)
    try:
        yield
    finally:
        _cost_ctx.reset(token)
        _flush(ctx)


def _flush(ctx: _CostCtx) -> None:
    if not ctx.buffer:
        return
    db = SessionLocal()
    try:
        for event in ctx.buffer:
            db.add(CostEvent(tenant_id=ctx.tenant_id, task_id=ctx.task_id, **event))
        db.commit()
    except Exception:  # noqa: BLE001 - 记账失败不影响任务结果
        db.rollback()
        logger.exception("批量写入费用事件失败")
    finally:
        db.close()
