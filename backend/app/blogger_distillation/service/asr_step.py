from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation.service.events import is_control_flow_exception, record_task_event
from app.blogger_distillation.service.extract import (
    extract_subtitle_urls,
    extract_video_url,
    fetch_subtitle_text,
    is_mostly_chinese,
    is_video_url_candidate,
    pick_video_stream,
    probe_remote_size,
    strip_asr_timestamps,
)
from app.blogger_distillation.tikhub_client import XhsPostCandidate
from app.models import BloggerPost, BloggerProfile


def _reuse_existing_transcript(
    db: Session, tenant_id: int, blogger: BloggerProfile, normalized: dict[str, Any]
) -> bool:
    """note_id 会随端点漂移,同一篇笔记可能被当成「新笔记」重抓 → 又跑一次昂贵的 ASR。
    入库前按稳定 note_key(biz_id)反查:若已存在同篇且已有有效转写,直接复用,跳过 ASR。"""
    note_key = (normalized.get("note_key") or "").strip()
    if not note_key:
        return False
    existing = db.scalar(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger.id,
            BloggerPost.note_key == note_key,
            BloggerPost.asr_status.in_(("succeeded", "subtitle")),
        )
    )
    if existing and (existing.transcript_text or "").strip():
        normalized["transcript_text"] = existing.transcript_text
        normalized["asr_status"] = existing.asr_status
        normalized["asr_error"] = ""
        return True
    return False


def handle_video_asr(
    db: Session,
    tenant_id: int,
    task_id: str,
    candidate: XhsPostCandidate,
    normalized: dict[str, Any],
    asr_provider: Any,
    blogger: BloggerProfile,
) -> None:
    # 优先复用历史转写(应对 note_id 漂移导致的重复采集),省下重复 ASR 成本。
    # 注:面向用户的进度文案里不出现 note_id/note_key/ASR/provider 这类技术词(见「进度文案净化」)。
    if _reuse_existing_transcript(db, tenant_id, blogger, normalized):
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", "这条视频之前转写过，直接复用")
        return
    if asr_provider is None:
        normalized["asr_status"] = "skipped"
        normalized["asr_error"] = "ASR 未开启或初始化失败"
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", "跳过这条视频的转写")
        return
    raw_payload = {}
    try:
        raw_payload = json.loads(normalized.get("raw_json") or "{}")
    except json.JSONDecodeError:
        raw_payload = {}
    # 小红书常挂中/英多条字幕轨。逐条取,优先用「中文」那条;只有英文(自动翻译)则丢弃改走 ASR。
    subtitle_urls = extract_subtitle_urls(candidate.raw) or extract_subtitle_urls(raw_payload)
    if subtitle_urls:
        record_task_event(db, tenant_id, task_id, "视频字幕", "running", "正在读取视频字幕…")
        non_chinese_seen = False
        for subtitle_url in subtitle_urls:
            try:
                subtitle_text = fetch_subtitle_text(subtitle_url)
            except Exception:
                record_task_event(db, tenant_id, task_id, "视频字幕", "succeeded", "这条字幕没读到，换用语音转文字")
                continue
            if not subtitle_text:
                continue
            if is_mostly_chinese(subtitle_text):
                normalized["transcript_text"] = subtitle_text
                normalized["asr_status"] = "subtitle"
                normalized["asr_error"] = ""
                record_task_event(
                    db, tenant_id, task_id, "视频字幕", "succeeded",
                    f"已用中文字幕（{len(subtitle_text)} 字），跳过语音转写",
                )
                return
            non_chinese_seen = True
        if non_chinese_seen:
            record_task_event(
                db, tenant_id, task_id, "视频字幕", "succeeded",
                "只有非中文字幕（疑似自动翻译），改用语音转文字",
            )
    # 选视频流:优先结构化 media.stream(pick_video_stream 含 size);否则从详情按「带音频优先」选——
    # extract_video_url → collect_video_url_candidates 已把无音频的 stream_type 16 排到最后(见 G1)。
    stream_info = pick_video_stream(candidate.raw) or pick_video_stream(raw_payload)
    video_url = (stream_info["url"] if stream_info else "") or extract_video_url(raw_payload) or extract_video_url(candidate.raw)
    if not is_video_url_candidate(video_url):
        video_url = ""
    if not video_url:
        normalized["asr_status"] = "skipped"
        normalized["asr_error"] = "未提取到可转写的视频 URL"
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", "没拿到视频直链，这条改用文字信息分析")
        return
    size_bytes = (stream_info or {}).get("size") or 0
    if not size_bytes:
        size_bytes = probe_remote_size(video_url)
    size_label = f"{size_bytes / (1 << 20):.1f}MB" if size_bytes else "未知"
    def on_progress(message: str) -> None:
        record_task_event(db, tenant_id, task_id, "视频 ASR", "running", message)

    try:
        record_task_event(
            db, tenant_id, task_id, "视频 ASR", "running",
            f"正在把视频语音转成文字…（视频 {size_label}）",
        )
        result = asr_provider.transcribe_video_url(video_url, source_id=candidate.external_id, on_progress=on_progress)
        normalized["transcript_text"] = strip_asr_timestamps(result.text)
        normalized["asr_status"] = "succeeded"
        normalized["asr_error"] = ""
        if result.duration_seconds:  # 供 content_subtype 密度判定用(字/秒);字幕/复用路径没有则留空
            normalized["duration_seconds"] = float(result.duration_seconds)
        record_task_event(
            db, tenant_id, task_id, "视频 ASR", "succeeded",
            f"视频转写完成（{len(result.text)} 字）",
            {"task_id": result.task_id, "duration_seconds": result.duration_seconds, "provider": result.provider},
        )
    except Exception as exc:
        if is_control_flow_exception(exc):
            raise  # 任务取消/超时不当作单条失败吞掉,一路上抛让任务干净失败(见 #20)
        normalized["asr_status"] = "skipped" if is_expected_asr_skip(exc) else "failed"
        normalized["asr_error"] = str(exc)
        event_status = "succeeded" if normalized["asr_status"] == "skipped" else "failed"
        record_task_event(db, tenant_id, task_id, "视频 ASR", event_status, "视频转写没跑成，这条改用文字信息分析")


def is_expected_asr_skip(exc: Exception) -> bool:
    message = str(exc)
    expected_markers = ("不包含音频流", "可能是图片封面", "未提取到视频 URL", "Invalid data found when processing input")
    return any(marker in message for marker in expected_markers)
