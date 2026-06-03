from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation import analysis
from app.blogger_distillation import artifacts
from app.blogger_distillation.asr import ASRError, build_asr_provider
from app.blogger_distillation.privacy import anonymize_comments
from app.blogger_distillation.quality import evaluate_post_quality, quality_report
from app.blogger_distillation.tikhub_client import (
    TikHubError,
    TikHubUsage,
    TikHubXhsClient,
    XhsPostCandidate,
    first_int,
    first_str,
    parse_timestamp,
    recursive_find,
    unwrap_payload,
)
from app.config import Settings
from app.models import (
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
    OperationTask,
    OperationTaskEvent,
    TaskStatus,
)
from app.services.ai_service import AIServiceError, create_json_response


logger = logging.getLogger(__name__)


@dataclass
class DistillationResult:
    run: BloggerDistillationRun
    skill: BloggerSkill


@dataclass
class CollectionResult:
    run: BloggerCollectionRun


class DistillationCancelled(Exception):
    pass


def record_task_event(
    db: Session,
    tenant_id: int,
    task_id: str,
    step_name: str,
    status: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    safe_message = truncate_task_event_message(message)
    logger.info("博主蒸馏事件：任务ID=%s，步骤=%s，状态=%s，%s", task_id, step_name, status, safe_message)
    try:
        db.add(
            OperationTaskEvent(
                tenant_id=tenant_id,
                task_id=task_id,
                step_name=step_name,
                status=status,
                message=safe_message,
                payload_json=json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("记录博主蒸馏事件失败：任务ID=%s，步骤=%s，状态=%s", task_id, step_name, status)


def truncate_task_event_message(message: str, limit: int = 480) -> str:
    normalized = " ".join(str(message).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def ensure_distillation_not_cancelled(db: Session, tenant_id: int, task_id: str) -> None:
    task = db.get(OperationTask, task_id)
    if not task or task.tenant_id != tenant_id:
        return
    db.refresh(task)
    if task.status in {TaskStatus.cancel_requested, TaskStatus.cancelled}:
        message = "用户已请求停止流程，流程安全退出；已采集样本会保留，未发布新的 Skill"
        record_task_event(db, tenant_id, task_id, "停止蒸馏", "cancelled", message)
        raise DistillationCancelled(message)


def archive_active_skills(db: Session, tenant_id: int, blogger_id: int) -> None:
    active_skills = db.scalars(
        select(BloggerSkill).where(
            BloggerSkill.tenant_id == tenant_id,
            BloggerSkill.blogger_id == blogger_id,
            BloggerSkill.status == "active",
        )
    )
    for skill in active_skills:
        skill.status = "archived"


def create_blogger(db: Session, tenant_id: int, display_name: str, homepage_url: str, niche: str, description: str) -> BloggerProfile:
    existing = db.scalar(
        select(BloggerProfile).where(BloggerProfile.tenant_id == tenant_id, BloggerProfile.homepage_url == homepage_url)
    )
    if existing:
        existing.display_name = display_name
        existing.niche = niche
        existing.description = description
        db.commit()
        db.refresh(existing)
        return existing
    blogger = BloggerProfile(
        tenant_id=tenant_id,
        platform="xhs",
        display_name=display_name,
        homepage_url=homepage_url,
        niche=niche,
        description=description,
    )
    db.add(blogger)
    db.commit()
    db.refresh(blogger)
    return blogger


def run_blogger_collection(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    sample_limit: int = 50,
    comments_per_post: int = 20,
    asr_enabled: bool = False,
) -> CollectionResult:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")

    run = BloggerCollectionRun(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        task_id=task_id,
        status="running",
        sample_limit=sample_limit,
        comments_per_post=comments_per_post,
        asr_enabled=asr_enabled,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    collection_settings = settings.model_copy(update={"asr_enabled": asr_enabled})

    client: TikHubXhsClient | None = None
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(db, tenant_id, task_id, "样本采集", "running", "开始采集数据")
        client = TikHubXhsClient(collection_settings)
        client.get_user_info(blogger.homepage_url)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        candidates = client.get_user_notes(blogger.homepage_url, sample_limit)
        record_task_event(db, tenant_id, task_id, "样本采集", "running", f"已获取笔记候选 {len(candidates)} 条")

        posts = collect_posts(db, tenant_id, task_id, blogger, client, collection_settings, candidates[:sample_limit], comments_per_post)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        if not posts:
            raise TikHubError("没有采集到可用的小红书笔记，请检查主页链接或 TikHub 接口返回")
        blogger.sample_count = len(posts)
        for position, post in enumerate(posts, 1):
            db.add(
                BloggerCollectionPost(
                    tenant_id=tenant_id,
                    blogger_id=blogger.id,
                    collection_run_id=run.id,
                    post_id=post.id,
                    position=position,
                )
            )
        record_task_event(db, tenant_id, task_id, "样本清洗", "succeeded", f"样本清洗完成：保留 {len(posts)} 条笔记")

        quality = quality_report(posts, sample_limit)
        if quality["warnings"]:
            record_task_event(db, tenant_id, task_id, "样本质量", "running", "；".join(quality["warnings"]), quality)
        else:
            record_task_event(db, tenant_id, task_id, "样本质量", "succeeded", "样本质量校验通过", quality)

        stats = analysis.analyze_posts(posts)
        stats["quality_report"] = quality
        run.status = "succeeded"
        run.post_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        run.summary_json = json.dumps({"stats": stats, "quality_report": quality}, ensure_ascii=False, default=str)
        apply_usage(run, client.usage)
        db.commit()
        db.refresh(run)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "基础统计",
            "succeeded",
            f"基础统计完成：爆款={len(stats['hot_posts'])}，评论={stats['comment_total']}，标题模式={len(stats['title_patterns'])}",
            {"collection_run_id": run.id},
        )
        return CollectionResult(run=run)
    except DistillationCancelled as exc:
        run.status = "cancelled"
        run.error_message = str(exc)
        if client:
            apply_usage(run, client.usage)
        db.commit()
        raise
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        if client:
            apply_usage(run, client.usage)
        db.commit()
        raise


def run_blogger_distillation(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    collection_run_id: int,
) -> DistillationResult:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    collection_run = db.get(BloggerCollectionRun, collection_run_id)
    if not collection_run or collection_run.tenant_id != tenant_id or collection_run.blogger_id != blogger.id:
        raise ValueError("采集批次不存在或不属于当前博主")
    if collection_run.status != "succeeded":
        raise ValueError("只能基于已完成的采集批次进行蒸馏")

    run = BloggerDistillationRun(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        collection_run_id=collection_run.id,
        task_id=task_id,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(db, tenant_id, task_id, "采集批次", "succeeded", f"使用采集批次 #{collection_run.id}，样本={collection_run.post_count}")
        post_ids = list(
            db.scalars(
                select(BloggerCollectionPost.post_id)
                .where(BloggerCollectionPost.collection_run_id == collection_run.id)
                .order_by(BloggerCollectionPost.position.asc(), BloggerCollectionPost.id.asc())
            )
        )
        posts = list(
            db.scalars(
                select(BloggerPost)
                .where(BloggerPost.id.in_(post_ids), BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger.id)
                .order_by(BloggerPost.score.desc(), BloggerPost.created_at.desc())
            )
        )
        if not posts:
            raise ValueError("采集批次没有可用于蒸馏的样本")
        record_task_event(db, tenant_id, task_id, "认知蒸馏", "running", "开始用大模型提炼认知、策略和执行层方法论")
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        stats = analysis.analyze_posts(posts)
        try:
            collection_summary = json.loads(collection_run.summary_json or "{}")
            if isinstance(collection_summary, dict) and collection_summary.get("quality_report"):
                stats["quality_report"] = collection_summary["quality_report"]
        except json.JSONDecodeError:
            pass
        user_info: dict[str, Any] = {"homepage_url": blogger.homepage_url, "nickname": blogger.display_name}
        distillation = distill_with_llm(settings, blogger, user_info, stats)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        usage = TikHubUsage()
        report_html = artifacts.render_report_html(blogger, stats, distillation, usage)
        skill_markdown = artifacts.build_skill_markdown(blogger, stats, distillation)
        archive_active_skills(db, tenant_id, blogger.id)
        skill = BloggerSkill(
            tenant_id=tenant_id,
            blogger_id=blogger.id,
            run_id=run.id,
            name=artifacts.slug_skill_name(blogger.display_name),
            description=f"基于小红书博主 {blogger.display_name} 公开内容蒸馏出的创作方法论",
            skill_markdown=skill_markdown,
            status="active",
        )
        db.add(skill)

        run.status = "succeeded"
        run.sample_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        run.tikhub_request_count = collection_run.tikhub_request_count
        run.tikhub_estimated_cost_usd = collection_run.tikhub_estimated_cost_usd
        run.tikhub_cost_min_usd = collection_run.tikhub_cost_min_usd
        run.tikhub_cost_max_usd = collection_run.tikhub_cost_max_usd
        run.report_json = json.dumps({"stats": stats, "distillation": distillation}, ensure_ascii=False, default=str)
        run.report_html = report_html
        blogger.last_distilled_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        db.refresh(skill)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "Skill 生成",
            "succeeded",
            f"蒸馏完成：批次 #{collection_run.id}",
            {"collection_run_id": collection_run.id, "run_id": run.id, "skill_id": skill.id},
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


def collect_posts(
    db: Session,
    tenant_id: int,
    task_id: str,
    blogger: BloggerProfile,
    client: TikHubXhsClient,
    settings: Settings,
    candidates: list[XhsPostCandidate],
    comments_per_post: int,
) -> list[BloggerPost]:
    posts: list[BloggerPost] = []
    asr_provider = None
    if settings.asr_enabled:
        try:
            asr_provider = build_asr_provider(settings)
            record_task_event(db, tenant_id, task_id, "视频 ASR", "running", f"ASR 已开启：provider={settings.asr_provider}")
        except ASRError as exc:
            record_task_event(db, tenant_id, task_id, "视频 ASR", "failed", f"ASR 初始化失败，将降级分析视频：{exc}")
            asr_provider = None
    else:
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", "ASR 未开启，视频笔记将使用标题、描述、评论和互动数据参与蒸馏")

    total = len(candidates)
    for index, candidate in enumerate(candidates, 1):
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "笔记详情",
            "running",
            "采集",
            {"current": index, "total": total, "type": candidate.note_type, "note_id": candidate.external_id},
        )
        try:
            detail_payload = client.get_image_note_detail(candidate)
        except TikHubError as exc:
            logger.warning("图文详情采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
            record_task_event(db, tenant_id, task_id, "笔记详情", "failed", f"详情采集失败：note_id={candidate.external_id}，错误={exc}")
            continue
        if candidate.note_type == "video" and not extract_video_url(detail_payload):
            detail_payload = supplement_video_detail_with_url(client, candidate, detail_payload)
        normalized = normalize_post(candidate, detail_payload)
        if not normalized["title"] and not normalized["body_text"]:
            record_task_event(db, tenant_id, task_id, "样本清洗", "failed", f"跳过空内容笔记：note_id={candidate.external_id}")
            continue
        if normalized["content_type"] == "video":
            ensure_distillation_not_cancelled(db, tenant_id, task_id)
            handle_video_asr(db, tenant_id, task_id, candidate, normalized, asr_provider)
            ensure_distillation_not_cancelled(db, tenant_id, task_id)
        comments = []
        try:
            ensure_distillation_not_cancelled(db, tenant_id, task_id)
            raw_comments = anonymize_comments(client.get_note_comments(candidate, comments_per_post))
            comments = [normalize_comment(item) for item in raw_comments]
        except TikHubError as exc:
            logger.warning("评论采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
            record_task_event(db, tenant_id, task_id, "评论采集", "failed", f"评论采集失败：note_id={candidate.external_id}，错误={exc}")
        normalized["comments_json"] = json.dumps([item for item in comments if item["content"]], ensure_ascii=False)
        post_quality = evaluate_post_quality(normalized)
        if post_quality.level == "failed":
            logger.warning("笔记质量不合格，跳过：note_id=%s，缺失=%s", candidate.external_id, ",".join(post_quality.missing))
            continue
        if post_quality.level == "partial":
            logger.info("笔记质量部分可用：note_id=%s，缺失=%s", candidate.external_id, ",".join(post_quality.missing))
        post = upsert_post(db, tenant_id, blogger, normalized)
        posts.append(post)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "样本入库",
            "succeeded",
            "已保存样本",
            {"current": index, "total": total, "post_id": post.id, "note_id": candidate.external_id, "asr": normalized["asr_status"]},
        )
    db.commit()
    return posts


def normalize_post(candidate: XhsPostCandidate, detail_payload: dict[str, Any]) -> dict[str, Any]:
    payload = unwrap_payload(detail_payload)
    raw = normalize_detail_payload(payload, detail_payload)
    counts = merge_interaction_counts(raw, candidate)
    hashtags = extract_hashtags(raw)
    media_urls = extract_media_urls(raw)
    video_url = extract_video_url(raw) or extract_video_url(detail_payload)
    if video_url and video_url not in media_urls:
        media_urls.insert(0, video_url)
    title = first_str(raw, ["title", "display_title", "note_title"]) or first_str(candidate.raw, ["display_title", "title"])
    body = first_str(raw, ["desc", "description", "content", "note_desc", "text"])
    url = first_str(raw, ["share_url", "url", "web_url"]) or first_str(candidate.raw, ["share_url", "url"])
    published_at = parse_timestamp(
        recursive_find(raw, "time") or recursive_find(raw, "timestamp") or recursive_find(raw, "last_update_time")
    )
    like_count = counts["like_count"]
    favorite_count = counts["favorite_count"]
    comment_count = counts["comment_count"]
    share_count = counts["share_count"]
    score = like_count * 0.35 + favorite_count * 0.45 + comment_count * 0.2 + share_count * 0.05
    return {
        "external_id": candidate.external_id,
        "url": url,
        "title": title[:500] or "未命名笔记",
        "body_text": body,
        "content_type": "video" if candidate.note_type == "video" or video_url else "image",
        "hashtags_json": json.dumps(hashtags, ensure_ascii=False),
        "cover_url": media_urls[0] if media_urls else "",
        "media_urls_json": json.dumps(media_urls, ensure_ascii=False),
        "transcript_text": "",
        "asr_status": "pending" if candidate.note_type == "video" else "not_required",
        "asr_error": "",
        "published_at": published_at,
        "like_count": like_count,
        "favorite_count": favorite_count,
        "comment_count": comment_count,
        "share_count": share_count,
        "score": score,
        "raw_json": json.dumps(detail_payload, ensure_ascii=False, default=str),
    }


def normalize_detail_payload(payload: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            note_card = first.get("noteCard") or first.get("note_card") or first.get("note")
            if isinstance(note_card, dict):
                merged = dict(note_card)
                for key in ("id", "note_id", "xsecToken", "xsec_token"):
                    if key in first and key not in merged:
                        merged[key] = first[key]
                return merged
            return first
    if isinstance(payload, dict):
        note_card = payload.get("noteCard") or payload.get("note_card") or payload.get("note")
        if isinstance(note_card, dict):
            merged = dict(note_card)
            for key in ("id", "note_id", "xsecToken", "xsec_token"):
                if key in payload and key not in merged:
                    merged[key] = payload[key]
            return merged
        return payload
    return fallback


def supplement_video_detail_with_url(client: TikHubXhsClient, candidate: XhsPostCandidate, fallback: dict[str, Any]) -> dict[str, Any]:
    for detail in client.get_video_note_detail_variants(candidate):
        if extract_video_url(detail):
            logger.info("视频 URL 补取成功：note_id=%s，端点=%s", candidate.external_id, detail.get("_endpoint_used", "<unknown>"))
            return detail
    return fallback


def merge_interaction_counts(raw: dict[str, Any], candidate: XhsPostCandidate) -> dict[str, int]:
    detail_counts = extract_counts_from_payload(raw)
    return {
        "like_count": detail_counts["like_count"] or candidate.like_count,
        "favorite_count": detail_counts["favorite_count"] or candidate.favorite_count,
        "comment_count": detail_counts["comment_count"] or candidate.comment_count,
        "share_count": detail_counts["share_count"] or candidate.share_count,
    }


def extract_counts_from_payload(raw: dict[str, Any]) -> dict[str, int]:
    interact = recursive_find(raw, "interact_info") or recursive_find(raw, "interactInfo")
    sources = collect_metric_sources(raw, interact)
    return {
        "like_count": first_positive_count(sources, ["liked_count", "liked_count_str", "likedCount", "like_count", "likeCount", "likes", "likeNum"]),
        "favorite_count": first_positive_count(
            sources,
            ["collected_count", "collected_count_str", "collectedCount", "favorite_count", "collect_count", "collects", "collectNum"],
        ),
        "comment_count": first_positive_count(
            sources,
            ["comment_count", "comment_count_str", "commentCount", "commentCountStr", "comments", "comment_num", "commentNum", "note_comment_count"],
        ),
        "share_count": first_positive_count(sources, ["share_count", "share_count_str", "shareCount", "sharedCount", "shares", "shareNum"]),
    }


def collect_metric_sources(raw: dict[str, Any], primary: Any | None = None) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add(value: Any) -> None:
        if not isinstance(value, dict) or id(value) in seen:
            return
        seen.add(id(value))
        sources.append(value)

    add(primary)
    for key in ("interact_info", "interactInfo", "note_card", "noteCard", "note", "stats", "statistics"):
        value = recursive_find(raw, key)
        add(value)
    add(raw)
    return sources


def first_positive_count(sources: list[dict[str, Any]], keys: list[str]) -> int:
    for source in sources:
        count = first_int(source, keys)
        if count > 0:
            return count
    return 0


def handle_video_asr(
    db: Session,
    tenant_id: int,
    task_id: str,
    candidate: XhsPostCandidate,
    normalized: dict[str, Any],
    asr_provider: Any,
) -> None:
    if asr_provider is None:
        normalized["asr_status"] = "skipped"
        normalized["asr_error"] = "ASR 未开启或初始化失败"
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", f"跳过视频转写：note_id={candidate.external_id}")
        return
    media_urls = []
    try:
        media_urls = json.loads(normalized.get("media_urls_json") or "[]")
    except json.JSONDecodeError:
        media_urls = []
    raw_payload = {}
    try:
        raw_payload = json.loads(normalized.get("raw_json") or "{}")
    except json.JSONDecodeError:
        raw_payload = {}
    subtitle_url = extract_subtitle_url(candidate.raw) or extract_subtitle_url(raw_payload)
    if subtitle_url:
        try:
            subtitle_text = fetch_subtitle_text(subtitle_url)
            if subtitle_text:
                normalized["transcript_text"] = subtitle_text
                normalized["asr_status"] = "subtitle"
                normalized["asr_error"] = ""
                record_task_event(
                    db,
                    tenant_id,
                    task_id,
                    "视频字幕",
                    "succeeded",
                    f"已使用视频字幕，跳过 ASR：note_id={candidate.external_id}，字数={len(subtitle_text)}",
                )
                return
        except Exception as exc:
            record_task_event(db, tenant_id, task_id, "视频字幕", "succeeded", f"字幕解析失败，继续尝试 ASR：note_id={candidate.external_id}，原因={exc}")
    candidate_video_url = extract_video_url(candidate.raw)
    candidate_urls = [candidate_video_url, *media_urls]
    video_url = next((url for url in candidate_urls if is_video_url_candidate(url)), "")
    if not video_url:
        normalized["asr_status"] = "skipped"
        normalized["asr_error"] = "未提取到可转写的视频 URL"
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", f"未拿到视频直链，跳过转写并降级分析：note_id={candidate.external_id}")
        return
    try:
        record_task_event(db, tenant_id, task_id, "视频 ASR", "running", f"开始转写视频：note_id={candidate.external_id}")
        result = asr_provider.transcribe_video_url(video_url, source_id=candidate.external_id)
        normalized["transcript_text"] = result.text
        normalized["asr_status"] = "succeeded"
        normalized["asr_error"] = ""
        record_task_event(
            db,
            tenant_id,
            task_id,
            "视频 ASR",
            "succeeded",
            f"视频转写完成：note_id={candidate.external_id}，字数={len(result.text)}，腾讯任务={result.task_id}",
            {"task_id": result.task_id, "duration_seconds": result.duration_seconds},
        )
    except Exception as exc:
        normalized["asr_status"] = "skipped" if is_expected_asr_skip(exc) else "failed"
        normalized["asr_error"] = str(exc)
        event_status = "succeeded" if normalized["asr_status"] == "skipped" else "failed"
        record_task_event(db, tenant_id, task_id, "视频 ASR", event_status, f"视频转写未执行，降级分析：note_id={candidate.external_id}，原因={exc}")


def normalize_comment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": first_str(item, ["content", "text", "comment_content", "desc"]),
        "like_count": first_int(item, ["like_count", "liked_count", "likes"]),
        "created_at": str(parse_timestamp(item.get("create_time") or item.get("time")) or ""),
    }


def upsert_post(db: Session, tenant_id: int, blogger: BloggerProfile, data: dict[str, Any]) -> BloggerPost:
    post = db.scalar(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger.id,
            BloggerPost.external_id == data["external_id"],
        )
    )
    if not post:
        post = BloggerPost(tenant_id=tenant_id, blogger_id=blogger.id, platform="xhs", **data)
        db.add(post)
        db.flush()
        return post
    for key, value in data.items():
        setattr(post, key, value)
    db.flush()
    return post


def extract_hashtags(raw: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    for key in ("tag_list", "hash_tag", "hashtags", "tags"):
        value = recursive_find(raw, key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    tags.add(item.lstrip("#"))
                elif isinstance(item, dict):
                    tag = first_str(item, ["name", "tag_name", "title"])
                    if tag:
                        tags.add(tag.lstrip("#"))
    text = " ".join([first_str(raw, ["title", "desc", "content"]), json.dumps(raw, ensure_ascii=False)[:2000]])
    for tag in re.findall(r"#([\w\u4e00-\u9fff-]+)", text):
        tags.add(tag)
    return sorted(tags)[:20]


def extract_media_urls(raw: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"url", "trace_id", "file_id"} and isinstance(child, str) and child.startswith("http"):
                    urls.append(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for key in ("image_list", "images_list", "images", "cover", "image"):
        value = recursive_find(raw, key)
        if value:
            visit(value)
    seen: set[str] = set()
    deduped = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped[:12]


def extract_video_url(raw: dict[str, Any]) -> str:
    video = recursive_find(raw, "video")
    if isinstance(video, dict):
        for url in extract_stream_urls(video):
            if is_likely_video_url(url):
                return url
        for key in ("videoUrl", "video_url", "play_url", "playUrl"):
            value = recursive_find(video, key)
            if is_likely_video_url(value):
                return value
    candidates = collect_video_url_candidates(raw)
    if candidates:
        return candidates[0]
    return ""


def extract_stream_urls(video: dict[str, Any]) -> list[str]:
    stream = ((video.get("media") or {}).get("stream") or video.get("stream") or {})
    if not isinstance(stream, dict):
        return []
    urls: list[str] = []
    for codec in ("h264", "h265", "av1"):
        items = stream.get(codec)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for key in ("masterUrl", "master_url", "main_url", "mainUrl", "url"):
                value = item.get(key)
                if isinstance(value, str):
                    urls.append(value)
            for key in ("backupUrls", "backup_urls", "backupUrl", "backup_url"):
                value = item.get(key)
                if isinstance(value, list):
                    urls.extend(url for url in value if isinstance(url, str))
                elif isinstance(value, str):
                    urls.append(value)
    return urls


def is_likely_video_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("http"):
        return False
    lowered = value.lower()
    if is_non_video_media_url(lowered):
        return False
    video_markers = (".mp4", ".mov", ".m3u8", ".ts", "video", "stream", "play", "sns-video")
    return any(marker in lowered for marker in video_markers)


def is_video_url_candidate(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("http"):
        return False
    return not is_non_video_media_url(value.lower())


def collect_video_url_candidates(raw: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, (*path, str(key)))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))
            return
        if not isinstance(value, str) or not value.startswith("http"):
            return
        lowered = value.lower()
        if is_non_video_media_url(lowered):
            return
        path_text = ".".join(path).lower()
        if is_subtitle_path(path_text):
            return
        if any(marker in path_text for marker in ("video", "stream", "play", "master", "m3u8", "h264", "h265")):
            if value not in seen:
                seen.add(value)
                candidates.append(value)

    visit(raw, ())
    return sorted(candidates, key=video_url_score, reverse=True)


def extract_subtitle_url(raw: dict[str, Any]) -> str:
    candidates: list[str] = []

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, (*path, str(key)))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))
            return
        if not isinstance(value, str) or not value.startswith("http"):
            return
        path_text = ".".join(path).lower()
        lowered = value.lower()
        if is_subtitle_path(path_text) or any(marker in lowered for marker in (".srt", ".vtt", "subtitle", "caption")):
            candidates.append(value)

    visit(raw, ())
    return candidates[0] if candidates else ""


def fetch_subtitle_text(subtitle_url: str) -> str:
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 PubSync/1.0"}) as client:
        response = client.get(subtitle_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        text = response.text
    if "json" in content_type:
        try:
            return extract_text_from_subtitle_json(response.json())
        except ValueError:
            pass
    return parse_subtitle_text(text)


def extract_text_from_subtitle_json(value: Any) -> str:
    fragments: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key.lower() in {"text", "content", "sentence", "word"} and isinstance(child, str):
                    fragments.append(child.strip())
                else:
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return normalize_transcript_text("\n".join(fragment for fragment in fragments if fragment))


def parse_subtitle_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("WEBVTT"):
            continue
        if stripped.isdigit() or "-->" in stripped:
            continue
        if re.match(r"^(NOTE|STYLE|REGION)\b", stripped, flags=re.IGNORECASE):
            continue
        lines.append(re.sub(r"<[^>]+>", "", stripped))
    return normalize_transcript_text("\n".join(lines))


def normalize_transcript_text(text: str) -> str:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def is_non_video_media_url(lowered_url: str) -> bool:
    image_markers = (".jpg", ".jpeg", ".png", ".webp", ".gif", "imageview", "image")
    subtitle_markers = (".srt", ".vtt", "subtitle", "caption", "subrip", "danmaku")
    return any(marker in lowered_url for marker in (*image_markers, *subtitle_markers))


def is_subtitle_path(path_text: str) -> bool:
    return any(marker in path_text for marker in ("subtitle", "caption", "subrip", "srt", "vtt", "danmaku"))


def video_url_score(url: str) -> int:
    lowered = url.lower()
    score = 0
    for marker in (".mp4", ".m3u8", "h264", "h265", "video", "stream", "play"):
        if marker in lowered:
            score += 10
    if "sns-video" in lowered:
        score += 20
    return score


def is_expected_asr_skip(exc: Exception) -> bool:
    message = str(exc)
    expected_markers = ("不包含音频流", "可能是图片封面", "未提取到视频 URL", "Invalid data found when processing input")
    return any(marker in message for marker in expected_markers)


def distill_with_llm(settings: Settings, blogger: BloggerProfile, user_info: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
你是“博主蒸馏 skill”的分析器。请参考 blogger-distiller 的方法：脚本负责事实统计，你负责把公开内容提炼成可迁移的创作方法论。

边界：
- 不能冒充原博主。
- 不能复制原文、标题、图片或个人经历。
- 只能提炼公开内容中的选题、结构、表达策略、评论需求和创作边界。
- 输出必须是合法 JSON，不要 Markdown，不要 HTML，不要解释过程。
- 你必须优先基于“代码统计与代表样本”，不要泛泛而谈。

博主：
{json.dumps({"display_name": blogger.display_name, "homepage_url": blogger.homepage_url, "niche": blogger.niche, "description": blogger.description}, ensure_ascii=False)}

TikHub 用户信息摘要：
{json.dumps(user_info, ensure_ascii=False, default=str)[:4000]}

代码统计与代表样本：
{json.dumps(stats, ensure_ascii=False, default=str)[:18000]}

重要口径：
- body_text / body_excerpt 只代表小红书笔记原始文字描述，不能混入视频字幕或 ASR 转写。
- transcript_text / transcript_excerpt 代表视频字幕或视频口播转写，属于“视频口播素材”，不是图文长文正文。
- structure_info 只描述图文正文结构；transcript_info 只描述视频口播/字幕结构。
- 如果样本以视频为主，必须分析“视频口播结构、切入方式、结尾方式、信息密度”，不要写成“长文模式”或“正文平均几千字”。
- 可以说“视频口播/字幕平均长度约 X 字”，但不能把这个数字当成图文正文长度。

输出 JSON：
{{
  "one_glance": "一句话说清这个账号的内容价值和爆款原因",
  "positioning": "这个博主公开内容呈现出的账号定位",
  "persona": ["人设拆解：身份感、表达姿态、信任来源"],
  "audience": "目标读者画像",
  "cognitive_model": ["认知层方法论"],
  "topic_strategy": ["选题策略"],
  "title_patterns": ["标题规律"],
  "opening_patterns": ["开头规律"],
  "body_structures": ["图文正文/笔记描述结构，只能基于 body_text/body_excerpt"],
  "video_script_structures": ["视频口播/字幕结构，只能基于 transcript_text/transcript_excerpt；如果没有视频转写则返回空数组"],
  "content_formula": ["可复用的内容公式"],
  "language_dna": ["语言风格、情绪节奏、常用表达方式"],
  "cover_text_rules": ["封面文案规律"],
  "hashtag_strategy": ["标签策略"],
  "comment_strategy": ["评论区洞察和互动策略"],
  "growth_insights": ["基于数据面板的发展趋势和机会"],
  "sample_topics": ["可迁移的新选题示例"],
  "contrast_examples": ["对比示例：普通写法 -> 更贴近该方法论的写法"],
  "do_not_do": ["禁止事项和不应模仿的部分"],
  "core_conclusion": "最后给用户的核心使用建议"
}}
"""
    data = create_json_response(settings, prompt)
    required = ["positioning", "audience", "cognitive_model", "topic_strategy", "title_patterns", "body_structures", "do_not_do"]
    for key in required:
        if key not in data:
            raise AIServiceError(f"博主蒸馏结果缺少字段：{key}")
    data.setdefault("one_glance", data.get("positioning", ""))
    data.setdefault("persona", [])
    data.setdefault("content_formula", data.get("body_structures", []))
    data.setdefault("video_script_structures", [])
    data.setdefault("language_dna", [])
    data.setdefault("growth_insights", [])
    data.setdefault("contrast_examples", [])
    data.setdefault("core_conclusion", data.get("positioning", ""))
    return data


def apply_usage(run: BloggerDistillationRun, usage: TikHubUsage) -> None:
    run.tikhub_request_count = usage.request_count
    run.tikhub_estimated_cost_usd = round(usage.estimated_cost_usd, 6)
    run.tikhub_cost_min_usd = round(usage.cost_min_usd, 6)
    run.tikhub_cost_max_usd = round(usage.cost_max_usd, 6)
