"""采集里的视觉步骤:对一篇笔记的封面/正文图跑 VLM,把图内文字 + 视觉摘要写进 normalized。

与 asr_step 对称。失败/无图只降级(vision_status=skipped/failed),绝不掀翻整批采集。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation.service.events import is_control_flow_exception, record_task_event
from app.blogger_distillation.tikhub_client import XhsPostCandidate
from app.blogger_distillation.vision import select_note_images
from app.config import Settings
from app.models import BloggerPost, BloggerProfile


def _reuse_existing_vision(db: Session, tenant_id: int, blogger: BloggerProfile, normalized: dict[str, Any]) -> bool:
    """同篇笔记(note_key 稳定)已成功解析过图片则复用,省掉重复 VLM 成本。"""
    note_key = (normalized.get("note_key") or "").strip()
    if not note_key:
        return False
    existing = db.scalar(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger.id,
            BloggerPost.note_key == note_key,
            BloggerPost.vision_status == "succeeded",
        )
    )
    if existing and ((existing.image_text or "").strip() or (existing.visual_digest or "").strip()):
        normalized["image_text"] = existing.image_text
        normalized["visual_digest"] = existing.visual_digest
        normalized["vision_status"] = "succeeded"
        normalized["vision_error"] = ""
        normalized["vision_image_count"] = existing.vision_image_count
        return True
    return False


def handle_note_vision(
    db: Session,
    tenant_id: int,
    task_id: str,
    candidate: XhsPostCandidate,
    normalized: dict[str, Any],
    vision_provider: Any,
    blogger: BloggerProfile,
    settings: Settings,
    scope: str | None = None,
) -> None:
    if _reuse_existing_vision(db, tenant_id, blogger, normalized):
        record_task_event(db, tenant_id, task_id, "图片理解", "succeeded", "这条的图片之前识别过，直接复用")
        return
    if vision_provider is None:
        normalized["vision_status"] = "skipped"
        normalized["vision_error"] = "视觉理解未开启或初始化失败"
        return
    try:
        media_urls = json.loads(normalized.get("media_urls_json") or "[]")
    except json.JSONDecodeError:
        media_urls = []
    images = select_note_images(
        normalized.get("cover_url") or "",
        media_urls if isinstance(media_urls, list) else [],
        scope=scope or settings.vision_scope,
        max_body_images=settings.vision_max_images_per_note,
    )
    if not images:
        normalized["vision_status"] = "skipped"
        normalized["vision_error"] = "无可解析图片"
        return

    def on_progress(message: str) -> None:
        record_task_event(db, tenant_id, task_id, "图片理解", "running", message)

    try:
        result = vision_provider.analyze_images(images, source_id=candidate.external_id, on_progress=on_progress)
        normalized["image_text"] = result.image_text
        normalized["visual_digest"] = json.dumps(result.visual_digest, ensure_ascii=False) if result.visual_digest else ""
        normalized["vision_status"] = "succeeded"
        normalized["vision_error"] = ""
        normalized["vision_image_count"] = result.image_count
        record_task_event(
            db,
            tenant_id,
            task_id,
            "图片理解",
            "succeeded",
            f"图片识别完成（识别 {result.image_count} 张、图内文字 {len(result.image_text)} 字）",
            {"image_count": result.image_count, "provider": result.provider},
        )
    except Exception as exc:
        if is_control_flow_exception(exc):
            raise  # 任务取消/超时不当作单条失败吞掉,一路上抛让任务干净失败(见 #20)
        normalized["vision_status"] = "failed"
        normalized["vision_error"] = str(exc)
        record_task_event(db, tenant_id, task_id, "图片理解", "failed", "图片识别没跑成，这条改用文字信息分析")


def revise_post_vision(post: BloggerPost, vision_provider: Any, settings: Settings) -> bool:
    """收尾补采:对已入库、图片理解失败的 post 当场重跑一次(此时采集并发峰值已过,成功率高)。

    直接改 post 的视觉字段;commit 由调用方负责。成功返回 True。控制流异常(取消/超时)照常上抛。
    """
    if vision_provider is None:
        return False
    try:
        media_urls = json.loads(post.media_urls_json or "[]")
    except json.JSONDecodeError:
        media_urls = []
    scope = "cover" if post.content_type == "video" else settings.vision_scope
    images = select_note_images(
        post.cover_url or "",
        media_urls if isinstance(media_urls, list) else [],
        scope=scope,
        max_body_images=settings.vision_max_images_per_note,
    )
    if not images:
        return False
    try:
        result = vision_provider.analyze_images(images, source_id=post.external_id)
    except Exception as exc:
        if is_control_flow_exception(exc):
            raise
        return False
    post.image_text = result.image_text
    post.visual_digest = json.dumps(result.visual_digest, ensure_ascii=False) if result.visual_digest else ""
    post.vision_status = "succeeded"
    post.vision_error = ""
    post.vision_image_count = result.image_count
    return True
