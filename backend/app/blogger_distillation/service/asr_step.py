from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.blogger_distillation.service.events import record_task_event
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
    # 小红书常挂中/英多条字幕轨。逐条取,优先用「中文」那条;只有英文(自动翻译)则丢弃改走 ASR。
    subtitle_urls = extract_subtitle_urls(candidate.raw) or extract_subtitle_urls(raw_payload)
    if subtitle_urls:
        non_chinese_seen = False
        for subtitle_url in subtitle_urls:
            try:
                subtitle_text = fetch_subtitle_text(subtitle_url)
            except Exception as exc:
                record_task_event(db, tenant_id, task_id, "视频字幕", "succeeded", f"字幕解析失败，换下一条/ASR：note_id={candidate.external_id}，原因={exc}")
                continue
            if not subtitle_text:
                continue
            if is_mostly_chinese(subtitle_text):
                normalized["transcript_text"] = subtitle_text
                normalized["asr_status"] = "subtitle"
                normalized["asr_error"] = ""
                record_task_event(
                    db,
                    tenant_id,
                    task_id,
                    "视频字幕",
                    "succeeded",
                    f"已使用中文字幕，跳过 ASR：note_id={candidate.external_id}，字数={len(subtitle_text)}",
                )
                return
            non_chinese_seen = True
        if non_chinese_seen:
            record_task_event(
                db, tenant_id, task_id, "视频字幕", "succeeded",
                f"只找到非中文字幕（疑似自动翻译），改走 ASR：note_id={candidate.external_id}",
            )
    stream_info = pick_video_stream(candidate.raw) or pick_video_stream(raw_payload)
    candidate_video_url = extract_video_url(candidate.raw)
    candidate_urls = [stream_info["url"] if stream_info else "", candidate_video_url, *media_urls]
    video_url = next((url for url in candidate_urls if is_video_url_candidate(url)), "")
    if not video_url:
        normalized["asr_status"] = "skipped"
        normalized["asr_error"] = "未提取到可转写的视频 URL"
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", f"未拿到视频直链，跳过转写并降级分析：note_id={candidate.external_id}")
        return
    size_bytes = (stream_info or {}).get("size") or 0
    if not size_bytes:
        size_bytes = probe_remote_size(video_url)
    size_label = f"{size_bytes / (1 << 20):.1f}MB" if size_bytes else "未知"
    def on_progress(message: str) -> None:
        record_task_event(db, tenant_id, task_id, "视频 ASR", "running", f"{message}（note_id={candidate.external_id}）")

    try:
        record_task_event(
            db,
            tenant_id,
            task_id,
            "视频 ASR",
            "running",
            f"检测到视频笔记且无字幕，视频大小 {size_label}，开始转写：note_id={candidate.external_id}",
        )
        result = asr_provider.transcribe_video_url(video_url, source_id=candidate.external_id, on_progress=on_progress)
        normalized["transcript_text"] = strip_asr_timestamps(result.text)
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


def is_expected_asr_skip(exc: Exception) -> bool:
    message = str(exc)
    expected_markers = ("不包含音频流", "可能是图片封面", "未提取到视频 URL", "Invalid data found when processing input")
    return any(marker in message for marker in expected_markers)
