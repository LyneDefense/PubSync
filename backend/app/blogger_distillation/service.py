from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

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
from app.models import BloggerDistillationRun, BloggerPost, BloggerProfile, BloggerSkill, OperationTask, OperationTaskEvent, TaskStatus
from app.services.ai_service import AIServiceError, create_json_response


logger = logging.getLogger(__name__)


@dataclass
class DistillationResult:
    run: BloggerDistillationRun
    skill: BloggerSkill


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
        message = "用户已请求停止蒸馏，流程安全退出；已采集样本会保留，未发布新的 Skill"
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


def run_blogger_distillation(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    sample_limit: int = 50,
    comments_per_post: int = 20,
    asr_enabled: bool | None = None,
) -> DistillationResult:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")

    run = BloggerDistillationRun(tenant_id=tenant_id, blogger_id=blogger.id, task_id=task_id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    effective_settings = settings.model_copy(update={"asr_enabled": asr_enabled}) if asr_enabled is not None else settings

    client: TikHubXhsClient | None = None
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(db, tenant_id, task_id, "博主采集", "running", "开始通过 TikHub 采集小红书图文笔记")
        client = TikHubXhsClient(effective_settings)
        user_info = client.get_user_info(blogger.homepage_url)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        candidates = client.get_user_notes(blogger.homepage_url, sample_limit)
        record_task_event(db, tenant_id, task_id, "博主采集", "running", f"已获取笔记候选 {len(candidates)} 条")

        posts = collect_posts(db, tenant_id, task_id, blogger, client, effective_settings, candidates[:sample_limit], comments_per_post)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        if not posts:
            raise TikHubError("没有采集到可用于蒸馏的图文笔记，请检查主页链接或 TikHub 接口返回")
        blogger.sample_count = len(posts)
        db.commit()
        record_task_event(db, tenant_id, task_id, "样本清洗", "succeeded", f"样本清洗完成：保留 {len(posts)} 条图文笔记")

        quality = quality_report(posts, sample_limit)
        if quality["warnings"]:
            record_task_event(db, tenant_id, task_id, "样本质量", "running", "；".join(quality["warnings"]), quality)
        else:
            record_task_event(db, tenant_id, task_id, "样本质量", "succeeded", "样本质量校验通过", quality)

        stats = analysis.analyze_posts(posts)
        stats["quality_report"] = quality
        record_task_event(
            db,
            tenant_id,
            task_id,
            "基础统计",
            "succeeded",
            f"基础统计完成：爆款={len(stats['hot_posts'])}，评论={stats['comment_total']}，标题模式={len(stats['title_patterns'])}",
        )

        record_task_event(db, tenant_id, task_id, "认知蒸馏", "running", "开始用大模型提炼认知、策略和执行层方法论")
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        distillation = distill_with_llm(effective_settings, blogger, user_info, stats)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        report_html = artifacts.render_report_html(blogger, stats, distillation, client.usage)
        skill_markdown = artifacts.build_skill_markdown(blogger, stats, distillation)
        archive_active_skills(db, tenant_id, blogger.id)
        skill = BloggerSkill(
            tenant_id=tenant_id,
            blogger_id=blogger.id,
            run_id=run.id,
            name=artifacts.slug_skill_name(blogger.display_name),
            description=f"基于小红书博主 {blogger.display_name} 公开图文内容蒸馏出的创作方法论",
            skill_markdown=skill_markdown,
            status="active",
        )
        db.add(skill)

        run.status = "succeeded"
        run.sample_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        apply_usage(run, client.usage)
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
            f"蒸馏完成：TikHub 请求={client.usage.request_count}，估算费用=${client.usage.estimated_cost_usd:.4f}",
            {"run_id": run.id, "skill_id": skill.id},
        )
        return DistillationResult(run=run, skill=skill)
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
            f"采集第 {index}/{total} 条：类型={candidate.note_type}，note_id={candidate.external_id}",
        )
        try:
            detail_payload = client.get_image_note_detail(candidate)
        except TikHubError as exc:
            logger.warning("图文详情采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
            record_task_event(db, tenant_id, task_id, "笔记详情", "failed", f"详情采集失败：note_id={candidate.external_id}，错误={exc}")
            continue
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
            f"已保存样本：类型={normalized['content_type']}，标题={normalized['title'][:40]}，ASR={normalized['asr_status']}",
            {"post_id": post.id, "note_id": candidate.external_id},
        )
    db.commit()
    return posts


def normalize_post(candidate: XhsPostCandidate, detail_payload: dict[str, Any]) -> dict[str, Any]:
    payload = unwrap_payload(detail_payload)
    raw = normalize_detail_payload(payload, detail_payload)
    counts = merge_interaction_counts(raw, candidate)
    hashtags = extract_hashtags(raw)
    media_urls = extract_media_urls(raw)
    video_url = extract_video_url(raw)
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
    sources = [item for item in (interact, raw) if isinstance(item, dict)]
    return {
        "like_count": first_positive_count(sources, ["liked_count", "liked_count_str", "likedCount", "like_count", "likeCount", "likes"]),
        "favorite_count": first_positive_count(
            sources,
            ["collected_count", "collected_count_str", "collectedCount", "favorite_count", "collect_count", "collects"],
        ),
        "comment_count": first_positive_count(sources, ["comment_count", "comment_count_str", "commentCount", "comments"]),
        "share_count": first_positive_count(sources, ["share_count", "share_count_str", "shareCount", "sharedCount", "shares"]),
    }


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
    video_url = next((url for url in media_urls if isinstance(url, str) and url.startswith("http")), "")
    if not video_url:
        normalized["asr_status"] = "failed"
        normalized["asr_error"] = "未提取到视频 URL"
        record_task_event(db, tenant_id, task_id, "视频 ASR", "failed", f"未提取到视频 URL：note_id={candidate.external_id}")
        return
    try:
        record_task_event(db, tenant_id, task_id, "视频 ASR", "running", f"开始转写视频：note_id={candidate.external_id}")
        result = asr_provider.transcribe_video_url(video_url, source_id=candidate.external_id)
        normalized["transcript_text"] = result.text
        normalized["asr_status"] = "succeeded"
        normalized["asr_error"] = ""
        if result.text:
            normalized["body_text"] = "\n\n".join(part for part in [normalized.get("body_text", ""), f"视频口播转写：{result.text}"] if part)
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
        normalized["asr_status"] = "failed"
        normalized["asr_error"] = str(exc)
        record_task_event(db, tenant_id, task_id, "视频 ASR", "failed", f"视频转写失败，降级分析：note_id={candidate.external_id}，错误={exc}")


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
    for key in ("videoUrl", "video_url", "masterUrl", "master_url", "play_url", "playUrl"):
        value = recursive_find(raw, key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    video = recursive_find(raw, "video")
    if isinstance(video, dict):
        stream = ((video.get("media") or {}).get("stream") or video.get("stream") or {})
        for codec in ("h264", "h265"):
            items = stream.get(codec)
            if isinstance(items, list) and items:
                url = items[0].get("masterUrl") or items[0].get("master_url")
                if isinstance(url, str) and url.startswith("http"):
                    return url
    return ""


def analyze_posts(posts: list[BloggerPost]) -> dict[str, Any]:
    sorted_posts = sorted(posts, key=lambda item: item.score, reverse=True)
    hot_count = min(10, max(3, int(len(sorted_posts) * 0.2))) if sorted_posts else 0
    hot_posts = sorted_posts[:hot_count]
    comments = []
    for post in posts:
        try:
            comments.extend(json.loads(post.comments_json or "[]"))
        except json.JSONDecodeError:
            continue
    return {
        "sample_count": len(posts),
        "comment_total": len(comments),
        "average_like": round(sum(item.like_count for item in posts) / max(len(posts), 1), 2),
        "average_favorite": round(sum(item.favorite_count for item in posts) / max(len(posts), 1), 2),
        "average_comment": round(sum(item.comment_count for item in posts) / max(len(posts), 1), 2),
        "favorite_like_ratio": round(sum(item.favorite_count for item in posts) / max(sum(item.like_count for item in posts), 1), 4),
        "title_patterns": detect_title_patterns(posts),
        "frequent_hashtags": frequent_hashtags(posts),
        "hot_posts": [post_summary(item) for item in hot_posts],
        "representative_posts": [post_summary(item) for item in sorted_posts[: min(20, len(sorted_posts))]],
        "comment_insights_source": comments[:100],
    }


def detect_title_patterns(posts: list[BloggerPost]) -> dict[str, int]:
    patterns = {
        "避坑型": r"别|不要|千万|踩坑|避坑|不建议",
        "数字清单型": r"\d+|一|二|三|四|五|六|七|八|九|十|几个|种|条",
        "问题型": r"为什么|怎么办|是不是|如何|怎么",
        "反常识型": r"其实|不是|反而|错了|真相",
        "人群定位型": r"新手|第一次|养猫人|养狗人|铲屎官|宝妈|打工人",
    }
    result = {key: 0 for key in patterns}
    for post in posts:
        for name, pattern in patterns.items():
            if re.search(pattern, post.title):
                result[name] += 1
    return result


def frequent_hashtags(posts: list[BloggerPost]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for post in posts:
        try:
            tags = json.loads(post.hashtags_json or "[]")
        except json.JSONDecodeError:
            tags = []
        for tag in tags:
            counts[str(tag)] = counts.get(str(tag), 0) + 1
    return [{"tag": tag, "count": count} for tag, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:20]]


def post_summary(post: BloggerPost) -> dict[str, Any]:
    comments = []
    try:
        comments = json.loads(post.comments_json or "[]")
    except json.JSONDecodeError:
        pass
    return {
        "id": post.id,
        "external_id": post.external_id,
        "title": post.title,
        "body_excerpt": post.body_text[:500],
        "hashtags": json.loads(post.hashtags_json or "[]"),
        "like_count": post.like_count,
        "favorite_count": post.favorite_count,
        "comment_count": post.comment_count,
        "score": round(post.score, 2),
        "url": post.url,
        "top_comments": comments[:10],
    }


def distill_with_llm(settings: Settings, blogger: BloggerProfile, user_info: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
你是“博主蒸馏 skill”的分析器。请参考 blogger-distiller 的方法：脚本负责事实统计，你负责把公开图文内容提炼成可迁移的创作方法论。

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
  "body_structures": ["正文结构"],
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
    data.setdefault("language_dna", [])
    data.setdefault("growth_insights", [])
    data.setdefault("contrast_examples", [])
    data.setdefault("core_conclusion", data.get("positioning", ""))
    return data


def render_report_html(blogger: BloggerProfile, stats: dict[str, Any], distillation: dict[str, Any], usage: TikHubUsage) -> str:
    sections = [
        ("账号定位", distillation.get("positioning")),
        ("目标读者", distillation.get("audience")),
        ("认知模型", distillation.get("cognitive_model")),
        ("选题策略", distillation.get("topic_strategy")),
        ("标题规律", distillation.get("title_patterns")),
        ("正文结构", distillation.get("body_structures")),
        ("评论洞察", distillation.get("comment_strategy")),
        ("禁止事项", distillation.get("do_not_do")),
    ]
    hot_items = "".join(
        f"<li><strong>{html.escape(item['title'])}</strong><span> 收藏 {item['favorite_count']} / 点赞 {item['like_count']} / 评论 {item['comment_count']}</span></li>"
        for item in stats.get("hot_posts", [])
    )
    body = [
        f"<h1>{html.escape(blogger.display_name)} 小红书图文蒸馏报告</h1>",
        f"<p>样本 {stats['sample_count']} 条，评论 {stats['comment_total']} 条，TikHub 请求 {usage.request_count} 次，估算费用 ${usage.estimated_cost_usd:.4f}（区间 ${usage.cost_min_usd:.4f} - ${usage.cost_max_usd:.4f}）。</p>",
        "<h2>爆款样本</h2>",
        f"<ol>{hot_items}</ol>",
    ]
    for title, value in sections:
        body.append(f"<h2>{html.escape(title)}</h2>")
        if isinstance(value, list):
            body.append("<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in value) + "</ul>")
        else:
            body.append(f"<p>{html.escape(str(value or ''))}</p>")
    return "\n".join(body)


def build_skill_markdown(blogger: BloggerProfile, stats: dict[str, Any], distillation: dict[str, Any]) -> str:
    name = slug_skill_name(blogger.display_name)
    return f"""---
name: {name}
description: 基于小红书博主 {blogger.display_name} 公开图文内容蒸馏出的创作方法论。不要冒充原博主，不要复制原文。
---

# {blogger.display_name} 图文创作方法论 Skill

## 角色定位

你不是原博主本人，不要冒充原博主。你是学习了该博主公开图文内容方法论的创作助手，只迁移选题、结构、表达策略和读者洞察。

## 适用范围

- 平台：小红书图文笔记，也可迁移到公众号短内容选题。
- 领域：{blogger.niche or "与样本内容相近的垂直领域"}。
- 样本规模：{stats["sample_count"]} 条图文笔记，{stats["comment_total"]} 条评论。

## 账号定位

{distillation.get("positioning", "")}

## 目标读者

{distillation.get("audience", "")}

## 认知模型

{markdown_list(distillation.get("cognitive_model"))}

## 选题策略

{markdown_list(distillation.get("topic_strategy"))}

## 标题规则

{markdown_list(distillation.get("title_patterns"))}

## 开头规则

{markdown_list(distillation.get("opening_patterns"))}

## 正文结构

{markdown_list(distillation.get("body_structures"))}

## 封面文案

{markdown_list(distillation.get("cover_text_rules"))}

## 话题标签

{markdown_list(distillation.get("hashtag_strategy"))}

## 评论区策略

{markdown_list(distillation.get("comment_strategy"))}

## 当用户不知道发什么时

1. 先询问账号定位、目标用户、发布目标和禁区。
2. 生成 20 个候选选题。
3. 按收藏潜力、评论潜力、账号匹配度评分。
4. 推荐前 5 个，并说明为什么适合。

## 当用户已有主题时

1. 判断主题是否适合该方法论。
2. 输出 3 个标题方案。
3. 输出正文、封面文案、话题标签、配图建议和评论引导。

## 可迁移选题示例

{markdown_list(distillation.get("sample_topics"))}

## 禁止事项

{markdown_list(distillation.get("do_not_do"))}
- 不复制原博主原文。
- 不复用原博主图片。
- 不冒充原博主身份。
- 不虚构个人经历、病例、数据或用户反馈。
"""


def markdown_list(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value) or "- 暂无"
    if value:
        return f"- {value}"
    return "- 暂无"


def slug_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", name.strip()).strip("-").lower()
    return f"xhs-{slug or 'blogger'}-distilled"


def apply_usage(run: BloggerDistillationRun, usage: TikHubUsage) -> None:
    run.tikhub_request_count = usage.request_count
    run.tikhub_estimated_cost_usd = round(usage.estimated_cost_usd, 6)
    run.tikhub_cost_min_usd = round(usage.cost_min_usd, 6)
    run.tikhub_cost_max_usd = round(usage.cost_max_usd, 6)
