from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.account_audit.agent import AuditContext, build_audit_agent
from app.blogger_distillation.service.events import record_task_event
from app.config import Settings
from app.models import AccountAuditRun, BloggerDistillationRun, BloggerProfile, BloggerSkill
from app.services.ai_service import is_ai_enabled, AIServiceError
from app.synthesis import humanize_event, run_agent
from app.xhs_creation.normalize import social_platform_name

logger = logging.getLogger(__name__)


def run_account_audit(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    platform: str,
    benchmark_skill_id: int,
    my_content_text: str,
) -> AccountAuditRun:
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    skill = db.get(BloggerSkill, benchmark_skill_id)
    if not skill or skill.tenant_id != tenant_id or skill.status != "active":
        raise ValueError("对标 Skill 不存在或不可用")
    blogger = db.get(BloggerProfile, skill.blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("对标 Skill 对应的博主不存在")
    if blogger.platform != platform:
        raise ValueError("对标 Skill 与所选平台不一致")

    run = AccountAuditRun(
        tenant_id=tenant_id,
        platform=platform,
        benchmark_blogger_id=blogger.id,
        benchmark_skill_id=skill.id,
        task_id=task_id,
        status="running",
        input_snapshot=my_content_text[:20000],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        record_task_event(db, tenant_id, task_id, "对标准备", "succeeded", f"对标博主:{blogger.display_name}")
        ctx = AuditContext(
            platform=platform,
            platform_name=social_platform_name(platform),
            benchmark_name=blogger.display_name,
            skill_markdown=skill.skill_markdown,
            my_content=my_content_text,
            benchmark_stats=_load_benchmark_stats(db, skill),
        )

        def on_event(kind: str, event: dict[str, Any]) -> None:
            triple = humanize_event(kind, event, subject="账号对比", gerund="分析")
            if triple:
                step, status, message = triple
                record_task_event(db, tenant_id, task_id, step, status, message)

        agent = build_audit_agent(settings, ctx)
        report, trace = run_agent(settings, agent, ctx, on_event=on_event)

        run.status = "succeeded"
        run.score = report.get("score")
        run.report_json = json.dumps(report, ensure_ascii=False, default=str)
        db.commit()
        db.refresh(run)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "账号对标",
            "succeeded",
            f"账号体检完成,对标接近度 {report.get('score')},自我修订 {trace.revisions} 次",
            {"run_id": run.id, "score": report.get("score"), "revisions": trace.revisions},
        )
        logger.info("账号体检完成:租户=%s,运行ID=%s,接近度=%s", tenant_id, run.id, report.get("score"))
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise


def _load_benchmark_stats(db: Session, skill: BloggerSkill) -> dict[str, Any]:
    run = db.get(BloggerDistillationRun, skill.run_id)
    if not run or not run.report_json:
        return {}
    try:
        report = json.loads(run.report_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    stats = report.get("stats") if isinstance(report, dict) else None
    return stats if isinstance(stats, dict) else {}
