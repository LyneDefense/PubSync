"""博主蒸馏的编排层:发起一次蒸馏(建 run → 取样本 → 调引擎 → 落 Skill/报告)、确认采纳、放弃。

LLM 那部分(提示词 / 合成循环 / 质量评分)在 :mod:`.distill_engine`。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation import analysis, artifacts
from app.blogger_distillation.modality import ALL as SCOPE_ALL
from app.blogger_distillation.service.crud import archive_active_skills
from app.blogger_distillation.service.distill_engine import (
    distill_with_llm,
    evaluate_distillation_quality,
    normalize_mode,
)
from app.blogger_distillation.service.events import (
    DistillationCancelled,
    ensure_distillation_not_cancelled,
    record_task_event,
)
from app.blogger_distillation.tikhub_client import TikHubUsage
from app.config import Settings
from app.models import (
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
)
from app.synthesis import humanize_event

logger = logging.getLogger(__name__)


@dataclass
class DistillationResult:
    run: BloggerDistillationRun
    skill: BloggerSkill


def build_distillation_diagnostics(posts: list[BloggerPost], stats: dict[str, Any]) -> dict[str, int]:
    stats_json = json.dumps(stats, ensure_ascii=False, default=str)
    return {
        "sample_count": len(posts),
        "video_count": sum(1 for post in posts if post.content_type == "video"),
        "transcript_count": sum(1 for post in posts if (post.transcript_text or "").strip()),
        "transcript_chars": sum(len(post.transcript_text or "") for post in posts),
        "comment_total": int(stats.get("comment_total") or 0),
        "stats_json_chars": len(stats_json),
        "stats_prompt_chars": min(len(stats_json), 18000),
    }


def run_blogger_distillation(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    post_ids: list[int],
    source: str = "custom",
    snapshot_id: int | None = None,
    mode: str = "A",
) -> DistillationResult:
    mode = normalize_mode(mode)
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    ids = [int(x) for x in (post_ids or [])]
    if not ids:
        raise ValueError("没有选择任何笔记")

    run = BloggerDistillationRun(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        collection_run_id=None,
        snapshot_id=snapshot_id,
        selection_json=json.dumps({"source": source, "post_ids": ids}, ensure_ascii=False),
        task_id=task_id,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        posts = list(
            db.scalars(
                select(BloggerPost)
                .where(
                    BloggerPost.id.in_(ids),
                    BloggerPost.tenant_id == tenant_id,
                    BloggerPost.blogger_id == blogger.id,
                    BloggerPost.status != "delisted",
                )
                .order_by(BloggerPost.score.desc(), BloggerPost.created_at.desc())
            )
        )
        if len(posts) < settings.distill_min_samples:
            raise ValueError(
                f"用于蒸馏的笔记只有 {len(posts)} 篇，至少需要 {settings.distill_min_samples} 篇"
                f"（建议 ≥{settings.distill_recommend_samples} 篇,样本越多越准）"
            )
        # 选材来源:自动=通用 skill;自定义=按所选笔记的模态推导 scope。
        if source == "auto":
            scope = [SCOPE_ALL]
        else:
            present = sorted({post.content_subtype for post in posts if post.content_subtype and post.content_subtype != "unknown"})
            scope = present or [SCOPE_ALL]
        record_task_event(
            db, tenant_id, task_id, "蒸馏选材", "succeeded",
            f"{'自动蒸馏(高赞)' if source == 'auto' else '自定义选材'}:{len(posts)} 篇笔记",
        )
        record_task_event(db, tenant_id, task_id, "认知蒸馏", "running", "开始用大模型提炼认知、策略和执行层方法论")
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        stats = analysis.analyze_posts(posts)
        user_info: dict[str, Any] = {"homepage_url": blogger.homepage_url, "nickname": blogger.display_name}
        diagnostics = build_distillation_diagnostics(posts, stats)
        logger.info(
            "认知蒸馏诊断：任务ID=%s，平台=%s，博主ID=%s，来源=%s，样本=%s，视频=%s，转写样本=%s，总转写字数=%s，评论=%s，stats字符=%s，发送字符=%s，模型=%s",
            task_id,
            blogger.platform,
            blogger.id,
            source,
            diagnostics["sample_count"],
            diagnostics["video_count"],
            diagnostics["transcript_count"],
            diagnostics["transcript_chars"],
            diagnostics["comment_total"],
            diagnostics["stats_json_chars"],
            diagnostics["stats_prompt_chars"],
            settings.minimax_text_model if settings.minimax_api_key else settings.openai_text_model,
        )
        llm_started_at = time.perf_counter()
        logger.info("认知蒸馏请求已发送：任务ID=%s，平台=%s，模型=%s", task_id, blogger.platform, settings.minimax_text_model if settings.minimax_api_key else settings.openai_text_model)

        def on_distill_event(kind: str, event: dict[str, Any]) -> None:
            triple = humanize_event(kind, event, subject="博主方法论", gerund="提炼")
            if triple:
                step, status, message = triple
                record_task_event(db, tenant_id, task_id, step, status, message)

        distillation, synthesis_trace = distill_with_llm(settings, blogger, user_info, stats, mode, on_event=on_distill_event)
        quality = evaluate_distillation_quality(distillation, stats, mode)
        quality["revisions"] = synthesis_trace.revisions
        quality["final_passed"] = synthesis_trace.final_passed
        llm_elapsed = time.perf_counter() - llm_started_at
        logger.info(
            "认知蒸馏返回：任务ID=%s，平台=%s，耗时=%.2fs，输出字段=%s，输出字符=%s",
            task_id,
            blogger.platform,
            llm_elapsed,
            len(distillation),
            len(json.dumps(distillation, ensure_ascii=False, default=str)),
        )
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        usage = TikHubUsage()
        report_html = artifacts.render_report_html(blogger, stats, distillation, usage, mode=mode, quality=quality)
        skill_markdown = artifacts.build_skill_markdown(blogger, stats, distillation, mode=mode, scope=scope)
        skill_desc = (
            f"基于你自己的小红书账号 {blogger.display_name} 蒸馏出的创作基因与增长诊断"
            if mode == "B"
            else f"基于小红书博主 {blogger.display_name} 公开内容蒸馏出的创作方法论"
        )
        skill = BloggerSkill(
            tenant_id=tenant_id,
            blogger_id=blogger.id,
            run_id=run.id,
            name=artifacts.slug_skill_name(blogger.display_name, mode),
            description=skill_desc,
            skill_markdown=skill_markdown,
            scope_json=json.dumps(scope, ensure_ascii=False),
            status="pending_confirmation",
        )
        db.add(skill)

        run.status = "pending_confirmation"
        run.sample_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        run.report_json = json.dumps(
            {"mode": mode, "stats": stats, "distillation": distillation, "quality": quality, "synthesis": synthesis_trace.to_dict()},
            ensure_ascii=False,
            default=str,
        )
        run.report_html = report_html
        db.commit()
        db.refresh(run)
        db.refresh(skill)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "Skill 生成",
            "succeeded",
            f"蒸馏完成，等待确认：质量评分 {quality['score']}（{quality['grade']}），自我修订 {synthesis_trace.revisions} 次",
            {
                "run_id": run.id,
                "skill_id": skill.id,
                "mode": mode,
                "quality_score": quality["score"],
                "quality_grade": quality["grade"],
                "revisions": synthesis_trace.revisions,
            },
        )
        return DistillationResult(run=run, skill=skill)
    except DistillationCancelled as exc:
        run.status = "cancelled"
        run.error_message = str(exc)
        db.commit()
        raise
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise


def confirm_blogger_distillation(db: Session, tenant_id: int, run_id: int) -> DistillationResult:
    run = db.get(BloggerDistillationRun, run_id)
    if not run or run.tenant_id != tenant_id:
        raise ValueError("蒸馏结果不存在或不属于当前工作空间")
    if run.status != "pending_confirmation":
        raise ValueError("只能保存待确认的蒸馏结果")
    blogger = db.get(BloggerProfile, run.blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("蒸馏结果对应的博主不存在")
    skill = db.scalar(
        select(BloggerSkill).where(
            BloggerSkill.tenant_id == tenant_id,
            BloggerSkill.blogger_id == blogger.id,
            BloggerSkill.run_id == run.id,
            BloggerSkill.status == "pending_confirmation",
        )
    )
    if not skill:
        raise ValueError("待确认 Skill 不存在")

    archive_active_skills(db, tenant_id, blogger.id)
    skill.status = "active"
    run.status = "succeeded"
    blogger.last_distilled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    db.refresh(skill)
    logger.info("博主蒸馏结果已保存：租户=%s，运行ID=%s，Skill ID=%s", tenant_id, run.id, skill.id)
    return DistillationResult(run=run, skill=skill)


def abandon_blogger_distillation(db: Session, tenant_id: int, run_id: int) -> BloggerDistillationRun:
    run = db.get(BloggerDistillationRun, run_id)
    if not run or run.tenant_id != tenant_id:
        raise ValueError("蒸馏结果不存在或不属于当前工作空间")
    if run.status != "pending_confirmation":
        raise ValueError("只能放弃待确认的蒸馏结果")
    skill = db.scalar(
        select(BloggerSkill).where(
            BloggerSkill.tenant_id == tenant_id,
            BloggerSkill.run_id == run.id,
            BloggerSkill.status == "pending_confirmation",
        )
    )
    if skill:
        skill.status = "abandoned"
    run.status = "abandoned"
    db.commit()
    db.refresh(run)
    logger.info("博主蒸馏结果已放弃：租户=%s，运行ID=%s", tenant_id, run.id)
    return run
