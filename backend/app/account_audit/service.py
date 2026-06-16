from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_audit.agent import AuditContext, build_audit_agent
from app.blogger_distillation.service.events import record_task_event
from app.config import Settings
from app.models import AccountAuditRun, BloggerPost, BloggerProfile
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
    kind: str,
    my_blogger_id: int,
    my_post_ids: list[int],
    benchmark_blogger_id: int | None = None,
    benchmark_post_ids: list[int] | None = None,
) -> AccountAuditRun:
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    kind = "self" if str(kind).strip().lower() == "self" else "benchmark"

    my_blogger = _require_blogger(db, tenant_id, platform, my_blogger_id, "我的账号")
    my_content = build_account_content(db, tenant_id, my_blogger_id, my_post_ids or [])
    if not my_content.strip():
        raise ValueError("请先为我的账号采集内容,并勾选要分析的内容")

    benchmark = None
    benchmark_content = ""
    if kind == "benchmark":
        if not benchmark_blogger_id:
            raise ValueError("请选择一个对标账号")
        benchmark = _require_blogger(db, tenant_id, platform, benchmark_blogger_id, "对标账号")
        benchmark_content = build_account_content(db, tenant_id, benchmark_blogger_id, benchmark_post_ids or [])
        if not benchmark_content.strip():
            raise ValueError("请先为对标账号采集内容,并勾选要对比的内容")

    snapshot = {
        "kind": kind,
        "my_blogger_id": my_blogger_id,
        "my_post_ids": my_post_ids,
        "benchmark_blogger_id": benchmark_blogger_id,
        "benchmark_post_ids": benchmark_post_ids,
    }
    run = AccountAuditRun(
        tenant_id=tenant_id,
        platform=platform,
        kind=kind,
        my_blogger_id=my_blogger_id,
        benchmark_blogger_id=benchmark.id if benchmark else None,
        task_id=task_id,
        status="running",
        input_snapshot=json.dumps(snapshot, ensure_ascii=False)[:20000],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        subject = "对标诊断" if kind == "benchmark" else "诊断我的"
        prep_msg = f"对标账号:{benchmark.display_name}" if benchmark else f"账号:{my_blogger.display_name}"
        record_task_event(db, tenant_id, task_id, f"{subject}准备", "succeeded", prep_msg)
        ctx = AuditContext(
            platform=platform,
            platform_name=social_platform_name(platform),
            kind=kind,
            my_name=my_blogger.display_name,
            my_content=my_content,
            benchmark_name=benchmark.display_name if benchmark else "",
            benchmark_content=benchmark_content,
        )

        def on_event(kind_: str, event: dict[str, Any]) -> None:
            triple = humanize_event(kind_, event, subject=subject, gerund="分析")
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
            subject,
            "succeeded",
            f"{subject}完成,评分 {report.get('score')},自我修订 {trace.revisions} 次",
            {"run_id": run.id, "score": report.get("score"), "revisions": trace.revisions},
        )
        logger.info("账号诊断完成:租户=%s,kind=%s,运行ID=%s,评分=%s", tenant_id, kind, run.id, report.get("score"))
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise


def _require_blogger(db: Session, tenant_id: int, platform: str, blogger_id: int, label: str) -> BloggerProfile:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError(f"{label}不存在")
    if blogger.platform != platform:
        raise ValueError(f"{label}与所选平台不一致")
    return blogger


def build_account_content(db: Session, tenant_id: int, blogger_id: int, post_ids: list[int]) -> str:
    """把所选 posts 拼成「标题+正文(+字幕)」文本,并附简单数据画像。无勾选时取该账号最近若干篇。"""
    stmt = select(BloggerPost).where(
        BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger_id
    )
    if post_ids:
        stmt = stmt.where(BloggerPost.id.in_(post_ids))
    stmt = stmt.order_by(BloggerPost.id.desc())
    posts = list(db.scalars(stmt))[:30]
    if not posts:
        return ""

    blocks: list[str] = []
    likes = favorites = comments = 0
    for idx, post in enumerate(posts, start=1):
        likes += post.like_count or 0
        favorites += post.favorite_count or 0
        comments += post.comment_count or 0
        body = (post.body_text or "").strip()
        transcript = (post.transcript_text or "").strip()
        piece = f"【{idx}】标题:{post.title or '(无标题)'}\n正文:{body[:600]}"
        if transcript:
            piece += f"\n口播/字幕:{transcript[:400]}"
        piece += f"\n互动:赞{post.like_count} 藏{post.favorite_count} 评{post.comment_count}"
        blocks.append(piece)

    n = len(posts)
    profile = f"共 {n} 篇 · 平均赞 {likes // n} / 藏 {favorites // n} / 评 {comments // n}"
    return profile + "\n\n" + "\n\n".join(blocks)
