"""单篇笔记的采集管线:按类型(图文/视频)分派到独立处理路径。

阶段 2「怎么采一篇」——阶段 1(选材/增量 diff)在 collection.py。
- 图文管线:正文 + 静态图,不碰 ASR/视频流。
- 视频管线:封面(静态图)做图片理解 + 视频流(带音频)做 ASR。
两条共享 详情/评论/图理解/质量/入库 等原子步骤;列表采集与 URL 定向采集都复用这里。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.blogger_distillation.asr import ASRError, build_asr_provider
from app.blogger_distillation.modality import assemble_video_profile_l0, classify_subtype, derive_video_tags
from app.blogger_distillation.privacy import anonymize_comments
from app.blogger_distillation.quality import evaluate_post_quality
from app.blogger_distillation.service.asr_step import handle_video_asr
from app.blogger_distillation.service.events import ensure_distillation_not_cancelled, record_task_event
from app.blogger_distillation.service.extract import (
    extract_video_url,
    normalize_comment,
    normalize_post,
    supplement_video_detail_with_url,
    upsert_post,
)
from app.blogger_distillation.service.motion_step import handle_video_motion
from app.blogger_distillation.service.vision_step import handle_note_vision
from app.blogger_distillation.tikhub_client import (
    TikHubDouyinClient,
    TikHubError,
    TikHubXhsClient,
    XhsPostCandidate,
)
from app.blogger_distillation.tikhub_client.parsers import detect_note_type
from app.blogger_distillation.vision import VisionError, build_vision_provider
from app.config import Settings
from app.models import BloggerPost, BloggerProfile

logger = logging.getLogger(__name__)

Client = TikHubXhsClient | TikHubDouyinClient


@dataclass
class CollectProviders:
    """一次采集共享的重型 provider(ASR / 视觉);初始化失败则为 None,对应步骤自动降级。"""

    asr: Any = None
    vision: Any = None


def build_collect_providers(db: Session, tenant_id: int, task_id: str, settings: Settings) -> CollectProviders:
    """按后台开关初始化 ASR / 视觉 provider,并记一次开启/降级事件。"""
    asr = None
    if settings.asr_enabled:
        try:
            asr = build_asr_provider(settings)
            record_task_event(db, tenant_id, task_id, "视频 ASR", "running", "已开启视频语音转写")
        except ASRError:
            record_task_event(db, tenant_id, task_id, "视频 ASR", "failed", "视频语音转写没能启动，改用文字信息分析")
    else:
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", "未开启视频语音转写，视频将用标题、描述、评论参与分析")
    vision = None
    if settings.vision_enabled:
        try:
            vision = build_vision_provider(settings)
            record_task_event(db, tenant_id, task_id, "图片理解", "running", "已开启图片识别")
        except VisionError:
            record_task_event(db, tenant_id, task_id, "图片理解", "failed", "图片识别没能启动，改用文字信息分析")
    return CollectProviders(asr=asr, vision=vision)


def process_one_note(
    db: Session,
    tenant_id: int,
    task_id: str,
    blogger: BloggerProfile,
    client: Client,
    settings: Settings,
    candidate: XhsPostCandidate,
    comments_per_post: int,
    providers: CollectProviders,
    *,
    current: int,
    total: int,
) -> BloggerPost | None:
    """采一篇:取详情 → 按类型分派到图文/视频管线。单篇失败返回 None,不掀翻整批。"""
    ensure_distillation_not_cancelled(db, tenant_id, task_id)
    record_task_event(
        db, tenant_id, task_id, "笔记详情", "running", f"正在采集第 {current}/{total} 篇笔记详情",
        {"current": current, "total": total, "type": candidate.note_type, "note_id": candidate.external_id},
    )
    try:
        detail = client.get_image_note_detail(candidate)
    except TikHubError as exc:
        logger.warning("笔记详情采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
        record_task_event(db, tenant_id, task_id, "笔记详情", "failed", "有一条笔记详情没采到，已跳过")
        return None
    note_type = candidate.note_type or detect_note_type(detail)
    pipeline = _process_video_note if note_type == "video" else _process_image_note
    return pipeline(db, tenant_id, task_id, blogger, client, settings, candidate, detail, comments_per_post, providers, current, total)


def _process_image_note(db, tenant_id, task_id, blogger, client, settings, candidate, detail, comments_per_post, providers, current, total):
    """图文管线:正文 + 静态图(封面 + 正文图)图片理解。不碰 ASR / 视频流。"""
    normalized = normalize_post(candidate, detail)
    if _is_empty_content(normalized):
        record_task_event(db, tenant_id, task_id, "样本清洗", "failed", "跳过一条空内容笔记")
        return None
    ensure_distillation_not_cancelled(db, tenant_id, task_id)
    handle_note_vision(db, tenant_id, task_id, candidate, normalized, providers.vision, blogger, settings)
    _collect_comments(db, tenant_id, task_id, client, candidate, normalized, comments_per_post)
    return _finalize_post(db, tenant_id, task_id, blogger, settings, candidate, normalized, current, total)


def _process_video_note(db, tenant_id, task_id, blogger, client, settings, candidate, detail, comments_per_post, providers, current, total):
    """视频管线:视频流(带音频)做 ASR + 封面(静态图)做图片理解。"""
    if not extract_video_url(detail):
        detail = supplement_video_detail_with_url(client, candidate, detail)
    normalized = normalize_post(candidate, detail)
    if _is_empty_content(normalized):
        record_task_event(db, tenant_id, task_id, "样本清洗", "failed", "跳过一条空内容笔记")
        return None
    ensure_distillation_not_cancelled(db, tenant_id, task_id)
    handle_video_asr(db, tenant_id, task_id, candidate, normalized, providers.asr, blogger)
    ensure_distillation_not_cancelled(db, tenant_id, task_id)
    # 视频只解析封面(scope=cover):正文图基本没有,省 GLM 开销。
    handle_note_vision(db, tenant_id, task_id, candidate, normalized, providers.vision, blogger, settings, scope="cover")
    ensure_distillation_not_cancelled(db, tenant_id, task_id)
    # 拍法(video_profile L1/L2:镜头切分 + 代表帧 VLM);受 video_motion_enabled 控,默认关。趁直链新鲜、刚下过一次做掉。
    handle_video_motion(db, tenant_id, task_id, candidate, normalized, providers.vision, blogger, settings)
    _collect_comments(db, tenant_id, task_id, client, candidate, normalized, comments_per_post)
    return _finalize_post(db, tenant_id, task_id, blogger, settings, candidate, normalized, current, total)


def _is_empty_content(normalized: dict[str, Any]) -> bool:
    return not normalized["title"] and not normalized["body_text"]


def _collect_comments(db, tenant_id, task_id, client, candidate, normalized, comments_per_post) -> None:
    """评论是附属信息:任何采集错误(含端点池全失败)都只跳过评论、继续采集,绝不掀翻整批。"""
    comments: list[dict[str, Any]] = []
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        raw_comments = anonymize_comments(client.get_note_comments(candidate, comments_per_post))
        comments = [normalize_comment(item) for item in raw_comments]
    except (TikHubError, RuntimeError) as exc:
        logger.warning("评论采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
        record_task_event(db, tenant_id, task_id, "评论采集", "failed", "有一条笔记的评论没采到，已跳过")
    normalized["comments_json"] = json.dumps([item for item in comments if item["content"]], ensure_ascii=False)


def _finalize_post(db, tenant_id, task_id, blogger, settings, candidate, normalized, current, total) -> BloggerPost | None:
    """定模态(T0平台+T1密度) → 质量校验 → upsert;质量不合格则跳过。"""
    subtype, confidence = classify_subtype(
        normalized["content_type"],
        normalized.get("transcript_text", ""),
        duration_seconds=normalized.get("duration_seconds"),
        density_high_cps=settings.modality_density_high_cps,
        density_low_cps=settings.modality_density_low_cps,
        min_transcript_chars=settings.talking_video_min_transcript_chars,
    )
    normalized["content_subtype"] = subtype
    normalized["content_subtype_confidence"] = confidence
    # 视频档案 L0(免费:现成字段)+ 派生标签。L1/L2(镜头/拍法)在 P1 补。content_subtype 仅作旧统计兼容,不再门控蒸馏。
    profile = assemble_video_profile_l0(
        normalized["content_type"],
        normalized.get("transcript_text", ""),
        normalized.get("duration_seconds"),
        density_high_cps=settings.modality_density_high_cps,
        density_low_cps=settings.modality_density_low_cps,
        min_transcript_chars=settings.talking_video_min_transcript_chars,
    )
    # 叠加拍法层(L1/L2,若采集时 motion_step 跑过);_motion 是内部键,必须 pop 掉再 upsert(否则 **data 塞非列会崩)。
    motion = normalized.pop("_motion", None)
    if profile and isinstance(motion, dict):
        profile.update(motion)
    normalized["video_profile"] = json.dumps(profile, ensure_ascii=False) if profile else ""
    tags = derive_video_tags(profile)
    normalized["video_tags"] = json.dumps(tags, ensure_ascii=False) if tags else ""
    post_quality = evaluate_post_quality(normalized)
    if post_quality.level == "failed":
        logger.warning("笔记质量不合格，跳过：note_id=%s，缺失=%s", candidate.external_id, ",".join(post_quality.missing))
        return None
    if post_quality.level == "partial":
        logger.info("笔记质量部分可用：note_id=%s，缺失=%s", candidate.external_id, ",".join(post_quality.missing))
    post = upsert_post(db, tenant_id, blogger, normalized)
    record_task_event(
        db, tenant_id, task_id, "样本入库", "succeeded", "已保存样本",
        {"current": current, "total": total, "post_id": post.id, "note_id": candidate.external_id,
         "asr": post.asr_status, "vision": post.vision_status or ""},
    )
    return post
