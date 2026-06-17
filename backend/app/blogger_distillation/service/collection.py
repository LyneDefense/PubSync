from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.blogger_distillation import analysis
from app.blogger_distillation.asr import ASRError, build_asr_provider
from app.blogger_distillation.privacy import anonymize_comments
from app.blogger_distillation.providers import ensure_collection_provider_available
from app.blogger_distillation.quality import evaluate_post_quality, quality_report
from app.blogger_distillation.service.asr_step import handle_video_asr
from app.blogger_distillation.service.events import (
    DistillationCancelled,
    ensure_distillation_not_cancelled,
    record_task_event,
)
from app.blogger_distillation.service.extract import (
    extract_video_url,
    normalize_comment,
    normalize_post,
    supplement_video_detail_with_url,
    upsert_post,
)
from app.blogger_distillation.service.usage import apply_usage
from app.blogger_distillation.tikhub_client import (
    TikHubDouyinClient,
    TikHubError,
    TikHubXhsClient,
    XhsPostCandidate,
)
from app.config import Settings
from app.models import BloggerCollectionPost, BloggerCollectionRun, BloggerPost, BloggerProfile

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    run: BloggerCollectionRun


def build_collection_client(settings: Settings, platform: str) -> TikHubXhsClient | TikHubDouyinClient:
    if platform == "douyin":
        return TikHubDouyinClient(settings)
    return TikHubXhsClient(settings)


def platform_collection_label(platform: str) -> str:
    return "抖音作品" if platform == "douyin" else "小红书笔记"


def _apply_auto_tags(
    db: Session,
    settings: Settings,
    tenant_id: int,
    task_id: str,
    blogger: BloggerProfile,
    posts: list[BloggerPost],
    stats: dict,
) -> None:
    """采集完成后用 LLM 给博主打内容标签。失败只记事件、绝不让采集失败。"""
    if not settings.blogger_auto_tag_enabled:
        return
    try:
        from app.blogger_distillation.service.tagging import generate_auto_tags, merge_tags

        record_task_event(db, tenant_id, task_id, "内容标签", "running", "正在提炼内容标签")
        model = (settings.blogger_tag_model or settings.distill_text_model or "").strip() or None
        limit = max(1, settings.blogger_tag_max)
        new_auto = generate_auto_tags(settings, blogger, posts, stats, model=model, limit=limit)
        blogger.tags_json = merge_tags(blogger.tags_json, new_auto, limit=limit)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "内容标签",
            "succeeded",
            f"已生成内容标签:{('、'.join(new_auto)) or '(无)'}",
            {"tags": new_auto},
        )
    except Exception as exc:  # noqa: BLE001 — 打标签是增强项,不能影响采集主流程
        logger.warning("自动打标签失败,跳过:blogger_id=%s,error=%s", blogger.id, exc)
        try:
            record_task_event(db, tenant_id, task_id, "内容标签", "running", f"内容标签生成失败,已跳过:{exc}")
        except Exception:  # noqa: BLE001
            pass


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

    client: TikHubXhsClient | TikHubDouyinClient | None = None
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(db, tenant_id, task_id, "样本采集", "running", "开始采集数据")
        ensure_collection_provider_available(blogger)
        client = build_collection_client(collection_settings, blogger.platform)
        client.get_user_info(blogger.homepage_url, blogger.external_id)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        candidates = client.get_user_notes(blogger.homepage_url, sample_limit, blogger.external_id)
        record_task_event(db, tenant_id, task_id, "样本采集", "running", f"已获取笔记候选 {len(candidates)} 条")

        posts = collect_posts(db, tenant_id, task_id, blogger, client, collection_settings, candidates[:sample_limit], comments_per_post)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        if not posts:
            raise TikHubError(f"没有采集到可用的{platform_collection_label(blogger.platform)}样本，请检查主页链接或 TikHub 接口返回")
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
        record_task_event(db, tenant_id, task_id, "样本清洗", "succeeded", f"样本清洗完成：保留 {len(posts)} 条样本")

        quality = quality_report(posts, sample_limit)
        if quality["warnings"]:
            record_task_event(db, tenant_id, task_id, "样本质量", "running", "；".join(quality["warnings"]), quality)
        else:
            record_task_event(db, tenant_id, task_id, "样本质量", "succeeded", "样本质量校验通过", quality)

        stats = analysis.analyze_posts(posts)
        stats["quality_report"] = quality
        _apply_auto_tags(db, settings, tenant_id, task_id, blogger, posts, stats)
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


def collect_posts(
    db: Session,
    tenant_id: int,
    task_id: str,
    blogger: BloggerProfile,
    client: TikHubXhsClient | TikHubDouyinClient,
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
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", "ASR 未开启，视频样本将使用标题、描述、评论和互动数据参与蒸馏")

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
