from __future__ import annotations

import argparse
import json
from typing import Any

from app.blogger_distillation.service import collect_video_url_candidates, extract_video_url, is_likely_video_url
from app.blogger_distillation.tikhub_client import TikHubXhsClient
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="诊断小红书博主笔记的视频 URL 提取情况")
    parser.add_argument("homepage_url", help="小红书博主主页链接")
    parser.add_argument("--limit", type=int, default=20, help="最多诊断多少条笔记，默认 20")
    parser.add_argument("--show-raw", action="store_true", help="打印疑似视频笔记的原始详情 JSON 顶层结构")
    args = parser.parse_args()

    settings = get_settings()
    client = TikHubXhsClient(settings)
    client.get_user_info(args.homepage_url)
    notes = client.get_user_notes(args.homepage_url, args.limit)

    print(f"共获取笔记候选：{len(notes)}")
    video_notes = [note for note in notes if note.note_type == "video"]
    print(f"其中视频笔记：{len(video_notes)}")
    print()

    for index, note in enumerate(video_notes, 1):
        print(f"===== 视频笔记 {index}/{len(video_notes)} =====")
        print(f"note_id: {note.external_id}")
        print(f"xsec_token: {note.xsec_token or '<empty>'}")
        print(f"列表页提取: {extract_video_url(note.raw) or '<none>'}")
        print(f"列表页候选: {len(collect_video_url_candidates(note.raw))}")
        try:
            detail = client.get_image_note_detail(note)
        except Exception as exc:
            print(f"详情页请求失败: {type(exc).__name__}: {exc}")
            print()
            continue
        detail_url = extract_video_url(detail)
        candidates = collect_video_url_candidates(detail)
        print(f"详情页提取: {detail_url or '<none>'}")
        print(f"详情页候选: {len(candidates)}")
        for candidate_index, candidate_url in enumerate(candidates[:10], 1):
            print(f"  候选 {candidate_index}: likely={is_likely_video_url(candidate_url)} {candidate_url[:260]}")
        if args.show_raw:
            print("详情页顶层结构:")
            print(json.dumps(summarize_shape(detail), ensure_ascii=False, indent=2)[:4000])
        print()

    print("TikHub 请求次数:", client.usage.request_count)
    print("TikHub 估算费用:", f"${client.usage.estimated_cost_usd:.4f}")


def summarize_shape(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        if isinstance(value, dict):
            return {"type": "dict", "keys": list(value.keys())[:20]}
        if isinstance(value, list):
            return {"type": "list", "length": len(value)}
        if isinstance(value, str):
            return value[:120]
        return value
    if isinstance(value, dict):
        return {str(key): summarize_shape(child, depth + 1) for key, child in list(value.items())[:30]}
    if isinstance(value, list):
        return [summarize_shape(child, depth + 1) for child in value[:3]]
    if isinstance(value, str):
        return value[:120]
    return value


if __name__ == "__main__":
    main()
