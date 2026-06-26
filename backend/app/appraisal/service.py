"""博主诊断编排:确保 ≥N 笔记 → 硬实力(算)+ 垂直度/软实力(模型)+ 合规 → 三区报告 → 存 AccountAuditRun。

两种目标:
- benchmark(诊断别人):硬 + 软(对路/可学/可蒸馏)+ 合规 → "值不值得对标"。
- self(诊断自己):硬 + 合规(+短改进提示),不出对标结论。

诊断必须基于真实笔记:没采过 → 自动补采到 N 条(增量);采过 → 直接用。
"""

from __future__ import annotations

import json
import logging
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.account_audit.service import build_account_content
from app.appraisal.hard import AccountStat, PostStat, hard_dimensions
from app.appraisal.judge import judge_soft, judge_vertical
from app.blogger_distillation.service import record_task_event, run_blogger_collection
from app.compliance import compliance_scan
from app.config import Settings
from app.models import AccountAuditRun, BloggerPost, BloggerProfile
from app.services.ai_service import AIServiceError, is_ai_enabled

logger = logging.getLogger(__name__)

HIGH = 70  # 维度均分 ≥ HIGH 视为「高」
MIN_DIAGNOSABLE = 5  # 少于这么多篇,诊断无意义


def run_appraisal(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    *,
    kind: str = "benchmark",
    intent: str = "",
    industry: str | None = None,
) -> AccountAuditRun:
    if not is_ai_enabled(settings):
        raise AIServiceError("未配置可用的大模型 API Key")
    kind = "self" if str(kind).strip().lower() == "self" else "benchmark"
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("账号不存在或不属于当前工作空间")
    platform = blogger.platform
    min_n = int(getattr(settings, "appraisal_min_samples", 20) or 20)
    sample_n = int(getattr(settings, "appraisal_sample_size", 30) or 30)

    run = AccountAuditRun(
        tenant_id=tenant_id,
        platform=platform,
        kind=kind,
        my_blogger_id=blogger_id if kind == "self" else None,
        benchmark_blogger_id=blogger_id if kind == "benchmark" else None,
        task_id=task_id,
        status="running",
        input_snapshot=json.dumps({"blogger_id": blogger_id, "kind": kind, "intent": intent, "industry": industry},
                                  ensure_ascii=False)[:20000],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        have = _active_count(db, tenant_id, blogger_id)
        if have < min_n:
            record_task_event(db, tenant_id, task_id, "采集样本", "running",
                              f"已有 {have} 篇,自动补采到约 {min_n} 篇再诊断…")
            run_blogger_collection(
                db=db, settings=settings, task_id=task_id, tenant_id=tenant_id, blogger_id=blogger_id,
                sample_limit=min_n, comments_per_post=0, asr_enabled=False, content_types=None,
                order="top_liked", fetch_all=False,
            )

        posts = list(db.scalars(
            select(BloggerPost)
            .where(BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger_id,
                   BloggerPost.status != "delisted")
            .order_by(BloggerPost.score.desc(), BloggerPost.id.desc())
            .limit(sample_n)
        ))
        if len(posts) < MIN_DIAGNOSABLE:
            raise ValueError(f"可用笔记仅 {len(posts)} 篇,不足以诊断(至少 {MIN_DIAGNOSABLE} 篇);请先在博主资产里多采集一些。")

        subject = "对标诊断" if kind == "benchmark" else "诊断我的账号"
        record_task_event(db, tenant_id, task_id, subject, "running", f"基于 {len(posts)} 篇笔记打分…")

        report = _diagnose(settings, blogger, posts, kind=kind, intent=intent, industry=industry,
                           db=db, tenant_id=tenant_id)

        run.status = "succeeded"
        run.score = report["hard_score"]
        run.report_json = json.dumps(report, ensure_ascii=False, default=str)
        db.commit()
        db.refresh(run)
        record_task_event(db, tenant_id, task_id, subject, "succeeded", report["headline"],
                          {"run_id": run.id, "hard_score": report["hard_score"],
                           "soft_score": report.get("soft_score"), "compliance_score": report["compliance"]["score"]})
        logger.info("博主诊断完成:租户=%s kind=%s 运行ID=%s 硬=%s 软=%s 合规=%s",
                    tenant_id, kind, run.id, report["hard_score"], report.get("soft_score"),
                    report["compliance"]["score"])
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise


def _active_count(db: Session, tenant_id: int, blogger_id: int) -> int:
    return db.scalar(
        select(func.count(BloggerPost.id)).where(
            BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger_id,
            BloggerPost.status != "delisted",
        )
    ) or 0


def _diagnose(settings, blogger, posts, *, kind, intent, industry, db, tenant_id) -> dict[str, Any]:
    """把硬实力(算)+ 垂直度/软实力(模型)+ 合规 串成三区报告。"""
    post_stats = [
        PostStat(likes=p.like_count or 0, collects=p.favorite_count or 0, comments=p.comment_count or 0,
                 published_at=p.published_at, content_type=p.content_type or "image")
        for p in posts
    ]
    total_lc = sum((p.like_count or 0) + (p.favorite_count or 0) for p in posts)
    acc = AccountStat(follower_count=blogger.follower_count or 0,
                      note_total=blogger.note_total or len(posts), total_like_collect=total_lc)

    hard = hard_dimensions(acc, post_stats) + [judge_vertical([p.title or "" for p in posts], settings)]
    hard_score = round(mean(d.score for d in hard))

    soft_dims: dict = {}
    soft_score = None
    if kind == "benchmark":
        brief = build_account_content(db, tenant_id, blogger.id, [p.id for p in posts])
        soft_dims = judge_soft(intent, brief, settings)
        soft_score = round(mean(d.score for d in soft_dims.values())) if soft_dims else None

    texts = [((p.title or "") + " " + (p.body_text or "")).strip() for p in posts]
    comp = compliance_scan(texts, blogger.platform, industry, settings=settings, use_llm=True)

    verdict = _verdict(kind, hard_score, soft_score, comp)
    return {
        "kind": kind,
        "intent": intent,
        "industry": industry,
        "sample_count": len(posts),
        "hard": [_dim_dict(d) for d in hard],
        "hard_score": hard_score,
        "soft": [_dim_dict(d) for d in soft_dims.values()],
        "soft_score": soft_score,
        "compliance": comp,
        "verdict": verdict,
        "headline": verdict["text"],
        "score": hard_score,
    }


def _dim_dict(d) -> dict[str, Any]:
    out = {"key": d.key, "label": d.label, "score": d.score, "detail": d.detail}
    if getattr(d, "metric", None):
        out["metric"] = d.metric
    if getattr(d, "extra", None):
        out["extra"] = d.extra
    if getattr(d, "evidence", None):
        out["evidence"] = d.evidence
    return out


def _verdict(kind: str, hard: int, soft: int | None, comp: dict) -> dict[str, str]:
    """三区联动结论(合规有否决权)。"""
    if kind == "self":
        if comp["has_ban"]:
            return {"level": "danger", "text": f"⚠️ 账号有封号级合规风险(合规分 {comp['score']}),建议尽快整改"}
        if hard >= HIGH:
            return {"level": "ok", "text": f"账号基本面不错(硬实力 {hard}),合规{comp['grade']}"}
        return {"level": "warn", "text": f"账号基本面偏弱(硬实力 {hard}),有提升空间"}

    # benchmark
    if comp["has_ban"]:
        return {"level": "danger",
                "text": "⚠️ 慎:它的打法踩了封号级红线,选题结构可以学,但违规话术别照搬"}
    s = soft if soft is not None else 0
    if hard >= HIGH and s >= HIGH:
        return {"level": "ok", "text": "强烈推荐对标:它牛、且对你路、打法干净"}
    if hard >= HIGH and s < HIGH:
        return {"level": "warn", "text": "它本身很牛,但方向/打法不太对你的路,选学"}
    if hard < HIGH and s >= HIGH:
        return {"level": "warn", "text": "方向对路,但它本身一般,学了天花板有限,只作补充"}
    return {"level": "muted", "text": "不太建议对标:本身一般、方向也不够贴"}
