"""采集里的视频拍法步骤(video_profile 的 L1/L2):镜头切分(节奏)+ 代表帧 VLM(风格)。

与 asr_step / vision_step 对称。在采集这条视频详情时做(此刻直链新鲜、且刚为 ASR 下过一次)。
受 `video_motion_enabled` 后台开关控制,默认关。失败/无流只降级,绝不掀翻整批。同篇 note_key 命中已到 L1/L2 则复用。

产物只塞进 `normalized["_motion"]`(L1/L2 字段字典);L0 基底 + 序列化 + 派生标签统一由 `_finalize_post` 做,避免覆盖。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation import video_frames
from app.blogger_distillation.service.events import is_control_flow_exception, note_title_label, record_task_event
from app.blogger_distillation.service.extract import extract_video_url, is_video_url_candidate, pick_video_stream
from app.blogger_distillation.tikhub_client import XhsPostCandidate
from app.config import Settings
from app.models import BloggerPost, BloggerProfile

logger = logging.getLogger(__name__)

_MOTION_FIELDS = ("on_camera", "hook_3s", "shot_style", "on_screen_text", "transitions", "style_summary")
# 归属 L1/L2 的键(节奏 + 拍法 + 层级);L0 的 duration/口播浓度由 _finalize_post 重算,不在此。
_L1L2_KEYS = ("layer", "shot_count", "avg_shot_s", "cuts_per_min", "pace", *_MOTION_FIELDS)


def _resolve_video_url(candidate: XhsPostCandidate, normalized: dict[str, Any]) -> str:
    """和 asr_step 同一套选流:优先结构化 stream,其次详情里的直链。取不到返回空。"""
    try:
        raw_payload = json.loads(normalized.get("raw_json") or "{}")
    except json.JSONDecodeError:
        raw_payload = {}
    stream = pick_video_stream(candidate.raw) or pick_video_stream(raw_payload)
    url = (stream["url"] if stream else "") or extract_video_url(raw_payload) or extract_video_url(candidate.raw)
    return url if is_video_url_candidate(url) else ""


def _reuse_existing_motion(db: Session, tenant_id: int, blogger: BloggerProfile, normalized: dict[str, Any]) -> bool:
    """同篇笔记(note_key 稳定)已抽到 L1/L2 则复用其拍法字段,省掉重复下载/切分/VLM。"""
    note_key = (normalized.get("note_key") or "").strip()
    if not note_key:
        return False
    existing = db.scalar(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger.id,
            BloggerPost.note_key == note_key,
        )
    )
    if not existing or not (existing.video_profile or "").strip():
        return False
    try:
        prof = json.loads(existing.video_profile)
    except (json.JSONDecodeError, ValueError):
        return False
    if isinstance(prof, dict) and prof.get("layer") in ("L1", "L2"):
        normalized["_motion"] = {k: prof[k] for k in _L1L2_KEYS if k in prof}
        return True
    return False


def handle_video_motion(
    db: Session,
    tenant_id: int,
    task_id: str,
    candidate: XhsPostCandidate,
    normalized: dict[str, Any],
    vision_provider: Any,
    blogger: BloggerProfile,
    settings: Settings,
) -> None:
    if not settings.video_motion_enabled or normalized.get("content_type") != "video":
        return
    label = note_title_label(normalized.get("title") or candidate.title) or "这条视频"
    if _reuse_existing_motion(db, tenant_id, blogger, normalized):
        record_task_event(db, tenant_id, task_id, "视频拍法", "succeeded", f"{label}之前分析过画面,直接复用")
        return
    video_url = _resolve_video_url(candidate, normalized)
    if not video_url:
        return
    try:
        record_task_event(db, tenant_id, task_id, "视频拍法", "running", f"正在分析{label}的镜头与节奏…")
        extract = video_frames.analyze_video_motion(settings, video_url)
        if extract is None:
            record_task_event(db, tenant_id, task_id, "视频拍法", "succeeded", f"{label}画面没分析成,改用文字/封面信息")
            return
        motion: dict = {**extract.pacing, "layer": "L1"}  # L1:镜头数/节奏
        # L2:代表帧 → VLM 拍法(出镜/景别/字幕/转场/一句话)。失败/无帧只保留 L1。
        if extract.frames and vision_provider is not None:
            desc = vision_provider.describe_motion(extract.frames, source_id=candidate.external_id)
            if isinstance(desc, dict):
                for key in _MOTION_FIELDS:
                    val = desc.get(key)
                    if val not in (None, ""):
                        motion[key] = val
                if any(motion.get(k) not in (None, "") for k in _MOTION_FIELDS):
                    motion["layer"] = "L2"
        normalized["_motion"] = motion
        record_task_event(
            db, tenant_id, task_id, "视频拍法", "succeeded",
            f"{label}画面分析完成（{motion.get('shot_count', '?')} 个镜头）",
        )
    except Exception as exc:
        if is_control_flow_exception(exc):
            raise  # 取消/超时照常上抛,不当单条失败吞掉
        logger.info("视频拍法分析失败,降级:note_id=%s,%s", candidate.external_id, exc)
        record_task_event(db, tenant_id, task_id, "视频拍法", "failed", f"{label}画面没跑成,改用文字/封面信息")
