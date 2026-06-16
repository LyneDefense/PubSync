from __future__ import annotations

from app.blogger_distillation.tikhub_client import TikHubUsage
from app.cost.context import record_tikhub
from app.models import BloggerDistillationRun


def apply_usage(run: BloggerDistillationRun, usage: TikHubUsage) -> None:
    run.tikhub_request_count = usage.request_count
    run.tikhub_estimated_cost_usd = round(usage.estimated_cost_usd, 6)
    run.tikhub_cost_min_usd = round(usage.cost_min_usd, 6)
    run.tikhub_cost_max_usd = round(usage.cost_max_usd, 6)
    # 费用台账:本次 run 的 TikHub 真实请求数与累计费用记一条(归属由 cost_capture 提供)。
    tablename = getattr(run, "__tablename__", "")
    kind = "collection" if "collection" in tablename else "distillation"
    if usage.request_count:
        record_tikhub(kind, usage.request_count, round(usage.estimated_cost_usd, 6))
