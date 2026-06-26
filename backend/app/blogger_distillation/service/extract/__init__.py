"""笔记规范化与媒体提取(无 DB 编排)。原 extract.py(543 行)按职责拆成三块,
这里原样再导出,调用方仍可 ``from app.blogger_distillation.service.extract import X``。

- :mod:`.post`     —— 笔记 / 评论规范化、互动数合并、话题 / 图片提取、upsert 落库
- :mod:`.video`    —— 视频直链提取(选流 / https / 打分排序 / URL 判别)
- :mod:`.subtitle` —— 字幕 / ASR 文本处理(找直链 / 下载解析 / 转写归一)
"""

from app.blogger_distillation.service.extract.post import (
    collect_metric_sources,
    extract_counts_from_payload,
    extract_hashtags,
    extract_media_urls,
    extract_note_key,
    first_positive_count,
    merge_interaction_counts,
    normalize_comment,
    normalize_detail_payload,
    normalize_post,
    supplement_video_detail_with_url,
    upsert_post,
)
from app.blogger_distillation.service.extract.subtitle import (
    extract_subtitle_url,
    extract_subtitle_urls,
    extract_text_from_subtitle_json,
    fetch_subtitle_text,
    is_mostly_chinese,
    normalize_transcript_text,
    parse_subtitle_text,
    strip_asr_timestamps,
)
from app.blogger_distillation.service.extract.video import (
    collect_video_url_candidates,
    extract_stream_urls,
    extract_video_url,
    is_likely_video_url,
    is_non_video_media_url,
    is_subtitle_path,
    is_video_url_candidate,
    pick_video_stream,
    probe_remote_size,
    to_https,
    video_url_score,
)

__all__ = [
    "collect_metric_sources",
    "extract_counts_from_payload",
    "extract_hashtags",
    "extract_media_urls",
    "extract_note_key",
    "first_positive_count",
    "merge_interaction_counts",
    "normalize_comment",
    "normalize_detail_payload",
    "normalize_post",
    "supplement_video_detail_with_url",
    "upsert_post",
    "extract_subtitle_url",
    "extract_subtitle_urls",
    "extract_text_from_subtitle_json",
    "fetch_subtitle_text",
    "is_mostly_chinese",
    "normalize_transcript_text",
    "parse_subtitle_text",
    "strip_asr_timestamps",
    "collect_video_url_candidates",
    "extract_stream_urls",
    "extract_video_url",
    "is_likely_video_url",
    "is_non_video_media_url",
    "is_subtitle_path",
    "is_video_url_candidate",
    "pick_video_stream",
    "probe_remote_size",
    "to_https",
    "video_url_score",
]
