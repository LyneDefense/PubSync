"""内容模态细分:采集时给每条笔记打 content_subtype,以及互动归一用的粗模态分组。

可扩展枚举(本轮小红书/抖音):
- image_text     图文
- talking_video  口播视频(语音驱动,转写又长又密)
- visual_video   非口播视频(混剪/卡点,几乎无语音)
- unknown        视频但 ASR 没开/无转写,判不了
预留(公众号):article / article_with_image —— 由结构(正文有无 <img>)判定,不需视觉模型。
"""

from __future__ import annotations

IMAGE_TEXT = "image_text"
TALKING_VIDEO = "talking_video"
VISUAL_VIDEO = "visual_video"
UNKNOWN = "unknown"
ALL = "__all__"

SUBTYPE_LABELS = {
    IMAGE_TEXT: "图文",
    TALKING_VIDEO: "口播视频",
    VISUAL_VIDEO: "非口播视频",
    UNKNOWN: "未知",
    "article": "纯文章",
    "article_with_image": "配图文章",
}


def subtype_label(subtype: str) -> str:
    return SUBTYPE_LABELS.get(subtype, subtype)


def classify_subtype(content_type: str, transcript_text: str, *, min_transcript_chars: int) -> str:
    """按 content_type + 转写密度启发式打标。纯函数,零 LLM。"""
    if content_type != "video":
        return IMAGE_TEXT
    transcript = (transcript_text or "").strip()
    if not transcript:
        return UNKNOWN
    if len(transcript) >= max(1, min_transcript_chars):
        return TALKING_VIDEO
    return VISUAL_VIDEO


def coarse_modality(content_type: str) -> str:
    """互动归一用的粗分组:image(图文)vs video(视频),与 content_type 对齐。"""
    return "video" if content_type == "video" else "image"


def candidate_modality(note_type: str) -> str:
    """采集前过滤用:候选笔记的粗模态(video / image)。"""
    return "video" if note_type == "video" else "image"
