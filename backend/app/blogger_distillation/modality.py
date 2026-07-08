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
TALKING_VIDEO = "talking_video"  # 旧 content_subtype 值,保留兼容(classify_subtype/存量)
VISUAL_VIDEO = "visual_video"    # 同上
VIDEO = "video"                  # 蒸馏内容层收敛后的「视频」车道(话术+拍法,按 content_type 路由)
UNKNOWN = "unknown"
ALL = "__all__"

SUBTYPE_LABELS = {
    IMAGE_TEXT: "图文",
    VIDEO: "视频",
    TALKING_VIDEO: "口播视频",
    VISUAL_VIDEO: "非口播视频",
    UNKNOWN: "未知",
    "article": "纯文章",
    "article_with_image": "配图文章",
}


def subtype_label(subtype: str) -> str:
    return SUBTYPE_LABELS.get(subtype, subtype)


# 判定置信来源。density/platform 高置信;ambiguous 待 T2 语义裁决;chars 无时长回退(中);unknown 判不了。
CONF_PLATFORM = "platform"
CONF_DENSITY = "density"
CONF_AMBIGUOUS = "ambiguous"
CONF_CHARS = "chars"
CONF_UNKNOWN = "unknown"
CONF_LLM = "llm"


def classify_subtype(
    content_type: str,
    transcript_text: str,
    *,
    duration_seconds: float | None = None,
    density_high_cps: float = 3.0,
    density_low_cps: float = 1.0,
    min_transcript_chars: int = 200,
) -> tuple[str, str]:
    """分级判定内容模态,返回 (subtype, confidence)。纯函数,零 LLM。

    T0 平台:非视频 → 图文(platform)。
    T1 密度(有时长):字/秒 ≥ high → 口播(density);≤ low → 非口播(density);之间 → 模糊(ambiguous,给密度最近猜测,交 T2)。
    回退(无时长,如字幕来源/旧数据):字数 ≥ 阈值 → 口播,否则非口播(chars,中置信)。
    视频但无转写(ASR 关/失败) → 未知(unknown)。
    """
    if content_type != "video":
        return IMAGE_TEXT, CONF_PLATFORM
    transcript = (transcript_text or "").strip()
    if not transcript:
        return UNKNOWN, CONF_UNKNOWN
    chars = len(transcript)
    if duration_seconds and duration_seconds > 0:
        cps = chars / duration_seconds  # 字/秒:整段说话密度
        if cps >= density_high_cps:
            return TALKING_VIDEO, CONF_DENSITY
        if cps <= density_low_cps:
            return VISUAL_VIDEO, CONF_DENSITY
        # 模糊带:密度既不高也不低(半口播/剧情/vlog)→ 先给最近猜测,标 ambiguous 交 T2 语义裁决
        provisional = TALKING_VIDEO if cps >= (density_low_cps + density_high_cps) / 2 else VISUAL_VIDEO
        return provisional, CONF_AMBIGUOUS
    # 无时长:字数回退(中置信),仍可被 T2 提升
    if chars >= max(1, min_transcript_chars):
        return TALKING_VIDEO, CONF_CHARS
    return VISUAL_VIDEO, CONF_CHARS


# —— 视频档案(video_profile)与派生标签 —— #
# 口播浓度:从「字/秒」派生的展示标签(none/low/mid/high),取代把视频拍成 talking/visual 的硬门。
NARRATION_LEVELS = ("none", "low", "mid", "high")
NARRATION_LABELS = {"none": "无口播", "low": "少量口播", "mid": "半口播", "high": "口播为主"}
PACE_LABELS = {"slow": "慢节奏", "medium": "中等节奏", "fast": "快节奏"}
ONCAMERA_LABELS = {True: "出镜", False: "画外音"}


def derive_narration_level(
    transcript_text: str,
    duration_seconds: float | None,
    *,
    density_high_cps: float = 3.0,
    density_low_cps: float = 1.0,
    min_transcript_chars: int = 200,
) -> str:
    """口播浓度:none(无转写)/ low / mid / high。有时长走字·秒,无时长按字数回退。纯函数。"""
    t = (transcript_text or "").strip()
    if not t:
        return "none"
    if duration_seconds and duration_seconds > 0:
        cps = len(t) / duration_seconds
        if cps >= density_high_cps:
            return "high"
        if cps <= density_low_cps:
            return "low"
        return "mid"
    return "mid" if len(t) >= max(1, min_transcript_chars) else "low"


def assemble_video_profile_l0(
    content_type: str,
    transcript_text: str,
    duration_seconds: float | None,
    *,
    density_high_cps: float = 3.0,
    density_low_cps: float = 1.0,
    min_transcript_chars: int = 200,
) -> dict:
    """采集时的免费档案层(L0):只用现成字段,零 LLM/下载。图文返回 {}。

    L1(镜头切分)/L2(代表帧)在 P1 由采集详情步补进同一个 dict(layer 前进到 L1/L2)。
    """
    if content_type != "video":
        return {}
    t = (transcript_text or "").strip()
    profile: dict = {"layer": "L0", "transcript_len": len(t)}
    if duration_seconds and duration_seconds > 0:
        profile["duration_s"] = round(float(duration_seconds), 1)
        if t:
            profile["speech_cps"] = round(len(t) / duration_seconds, 2)
    profile["narration_level"] = derive_narration_level(
        t, duration_seconds,
        density_high_cps=density_high_cps, density_low_cps=density_low_cps, min_transcript_chars=min_transcript_chars,
    )
    return profile


def derive_video_tags(profile: dict | None) -> dict:
    """从 video_profile 派生展示/筛选标签。随层数变丰富:L0→口播浓度,L1→节奏,L2→出镜。纯函数、可重算。"""
    if not profile:
        return {}
    tags: dict = {}
    if profile.get("narration_level"):
        tags["narration_level"] = profile["narration_level"]
    if profile.get("pace"):
        tags["pace"] = profile["pace"]
    if "on_camera" in profile:
        tags["on_camera"] = profile["on_camera"]
    return tags


def coarse_modality(content_type: str) -> str:
    """互动归一用的粗分组:image(图文)vs video(视频),与 content_type 对齐。"""
    return "video" if content_type == "video" else "image"


def candidate_modality(note_type: str) -> str:
    """采集前过滤用:候选笔记的粗模态(video / image)。"""
    return "video" if note_type == "video" else "image"
