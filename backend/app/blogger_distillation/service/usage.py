from __future__ import annotations

from app.blogger_distillation.tikhub_client import TikHubUsage
from app.models import BloggerDistillationRun


def apply_usage(run: BloggerDistillationRun, usage: TikHubUsage) -> None:
    run.tikhub_request_count = usage.request_count
    run.tikhub_estimated_cost_usd = round(usage.estimated_cost_usd, 6)
    run.tikhub_cost_min_usd = round(usage.cost_min_usd, 6)
    run.tikhub_cost_max_usd = round(usage.cost_max_usd, 6)
