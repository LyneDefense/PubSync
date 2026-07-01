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
from app.blogger_distillation.modality import (
    IMAGE_TEXT,
    TALKING_VIDEO,
    VISUAL_VIDEO,
    subtype_label,
)
from app.blogger_distillation.service.crud import archive_active_skills
from app.blogger_distillation.service.distill_engine import (
    distill_core,
    distill_lane,
    evaluate_core_quality,
    evaluate_lane_quality,
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
        record_task_event(
            db, tenant_id, task_id, "蒸馏选材", "succeeded",
            f"{'自动蒸馏(高赞)' if source == 'auto' else '自定义选材'}:{len(posts)} 篇笔记",
        )
        stats = analysis.analyze_posts(posts)  # 内核 stats(全账号,跨模态)
        user_info: dict[str, Any] = {"homepage_url": blogger.homepage_url, "nickname": blogger.display_name}

        def on_distill_event(kind: str, event: dict[str, Any]) -> None:
            triple = humanize_event(kind, event, subject="博主方法论", gerund="提炼")
            if triple:
                step, status, message = triple
                record_task_event(db, tenant_id, task_id, step, status, message)

        llm_started_at = time.perf_counter()
        # 1) 内核蒸馏(认知/策略/人设,吃全部笔记含 unknown)。
        record_task_event(db, tenant_id, task_id, "内核蒸馏", "running", "提炼这个人的认知层、策略层与人设(跨模态)")
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        core, core_trace = distill_core(settings, blogger, user_info, stats, mode, on_event=on_distill_event)
        core_quality = evaluate_core_quality(core, stats, mode)

        # 2) 内容层按 content_subtype 分车道蒸馏;样本不足的车道诚实跳过。
        lane_posts: dict[str, list[BloggerPost]] = {IMAGE_TEXT: [], TALKING_VIDEO: [], VISUAL_VIDEO: []}
        for post in posts:
            if post.content_subtype in lane_posts:
                lane_posts[post.content_subtype].append(post)
        unknown_count = len(posts) - sum(len(v) for v in lane_posts.values())
        min_lane = settings.distill_min_samples_per_subtype
        content_lanes: dict[str, Any] = {}
        lane_quality: dict[str, Any] = {}
        skipped: list[str] = []
        total_revisions = core_trace.revisions
        for lane, lps in lane_posts.items():
            if len(lps) < min_lane:
                if lps:
                    skipped.append(f"{subtype_label(lane)}(仅{len(lps)}篇,<{min_lane})")
                continue
            ensure_distillation_not_cancelled(db, tenant_id, task_id)
            lane_stats = analysis.analyze_posts(lps)
            record_task_event(db, tenant_id, task_id, "内容层", "running", f"蒸馏{subtype_label(lane)}写法({len(lps)}篇)")
            content, lane_trace = distill_lane(settings, blogger, user_info, lane, lane_stats, mode, on_event=on_distill_event)
            content["sample_count"] = len(lps)
            content_lanes[lane] = content
            lane_quality[lane] = evaluate_lane_quality(content, lane_stats, lane)
            total_revisions += lane_trace.revisions

        # 兜底:一条车道都不够(小号)→ 对全部笔记走一次内容层,标「综合」,不让内容层空着。
        if not content_lanes:
            dominant = max(lane_posts, key=lambda k: len(lane_posts[k])) if any(lane_posts.values()) else IMAGE_TEXT
            content, lane_trace = distill_lane(settings, blogger, user_info, dominant, stats, mode, on_event=on_distill_event)
            content["sample_count"] = len(posts)
            content["mixed"] = True
            content_lanes[dominant] = content
            lane_quality[dominant] = evaluate_lane_quality(content, stats, dominant)
            total_revisions += lane_trace.revisions
            skipped.append("样本不足未分车道,内容层基于全部笔记(综合)")

        # 3) 合并结果 + 组合质量分。
        lane_coverage = {
            IMAGE_TEXT: len(lane_posts[IMAGE_TEXT]), TALKING_VIDEO: len(lane_posts[TALKING_VIDEO]),
            VISUAL_VIDEO: len(lane_posts[VISUAL_VIDEO]), "unknown": unknown_count, "skipped": skipped,
        }
        distillation = {**core, "content_lanes": content_lanes, "lane_coverage": lane_coverage}
        lane_scores = [q["score"] for q in lane_quality.values()]
        combined = round((core_quality["score"] + sum(lane_scores)) / (1 + len(lane_scores))) if lane_scores else core_quality["score"]
        all_issues = list(core_quality.get("issues", []))
        for lane_key, lane_q in lane_quality.items():
            all_issues += [f"[{subtype_label(lane_key)}] {i}" for i in lane_q.get("issues", [])]
        quality = {
            "score": combined, "grade": "优" if combined >= 85 else ("良" if combined >= 70 else "待改进"),
            "issues": all_issues, "core": core_quality, "lanes": lane_quality, "lane_coverage": lane_coverage,
            "revisions": total_revisions, "final_passed": core_trace.final_passed,
        }
        scope = list(content_lanes.keys()) or [SCOPE_ALL]  # 技能 scope 天然 = 实际产出的车道
        llm_elapsed = time.perf_counter() - llm_started_at
        logger.info(
            "蒸馏完成：任务ID=%s，平台=%s，provider=%s，耗时=%.2fs，车道=%s，跳过=%s，综合分=%s",
            task_id, blogger.platform, settings.llm_provider, llm_elapsed, list(content_lanes.keys()), skipped, combined,
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
            {"mode": mode, "stats": stats, "distillation": distillation, "quality": quality, "synthesis": core_trace.to_dict()},
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
            f"蒸馏完成，等待确认：质量评分 {quality['score']}（{quality['grade']}），自我修订 {total_revisions} 次",
            {
                "run_id": run.id,
                "skill_id": skill.id,
                "mode": mode,
                "quality_score": quality["score"],
                "quality_grade": quality["grade"],
                "revisions": total_revisions,
                "lanes": list(content_lanes.keys()),
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
