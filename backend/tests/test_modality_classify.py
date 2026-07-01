"""内容模态分级判定(T0平台 + T1密度 + 回退)单测 + T2 裁决标签映射。"""

from app.blogger_distillation.modality import (
    IMAGE_TEXT,
    TALKING_VIDEO,
    UNKNOWN,
    VISUAL_VIDEO,
    classify_subtype,
)
from app.blogger_distillation.modality_adjudicator import _label_to_subtype

HIGH, LOW = 3.0, 1.0


def _cls(content_type, transcript, duration=None):
    return classify_subtype(
        content_type, transcript, duration_seconds=duration,
        density_high_cps=HIGH, density_low_cps=LOW, min_transcript_chars=200,
    )


def test_t0_image_is_platform():
    assert _cls("image", "") == (IMAGE_TEXT, "platform")
    assert _cls("image", "随便") == (IMAGE_TEXT, "platform")


def test_video_no_transcript_is_unknown():
    assert _cls("video", "", duration=60) == (UNKNOWN, "unknown")
    assert _cls("video", "   ", duration=None) == (UNKNOWN, "unknown")


def test_t1_density_high_is_talking():
    # 400 字 / 60 秒 = 6.7 字/秒 ≥ 3 → 口播(高置信)
    assert _cls("video", "字" * 400, duration=60) == (TALKING_VIDEO, "density")


def test_t1_density_low_is_visual():
    # 30 字 / 60 秒 = 0.5 字/秒 ≤ 1 → 非口播(高置信)
    assert _cls("video", "字" * 30, duration=60) == (VISUAL_VIDEO, "density")


def test_t1_density_ambiguous_band():
    # 120 字 / 60 秒 = 2.0 字/秒,落在 (1,3) 模糊带 → ambiguous(交 T2);2.0≥中点2 → 临时猜口播
    subtype, conf = _cls("video", "字" * 120, duration=60)
    assert conf == "ambiguous"
    assert subtype == TALKING_VIDEO
    # 90 字 / 60 秒 = 1.5 < 中点2 → 临时猜非口播,仍 ambiguous
    subtype2, conf2 = _cls("video", "字" * 90, duration=60)
    assert conf2 == "ambiguous" and subtype2 == VISUAL_VIDEO


def test_char_fallback_without_duration():
    # 无时长 → 字数回退(中置信 chars)
    assert _cls("video", "字" * 250, duration=None) == (TALKING_VIDEO, "chars")
    assert _cls("video", "字" * 50, duration=None) == (VISUAL_VIDEO, "chars")
    assert _cls("video", "字" * 250, duration=0) == (TALKING_VIDEO, "chars")  # duration=0 视为无时长


def test_adjudicator_label_mapping():
    assert _label_to_subtype("口播") == TALKING_VIDEO
    assert _label_to_subtype("非口播") == VISUAL_VIDEO
    assert _label_to_subtype("剧情") == VISUAL_VIDEO
    assert _label_to_subtype("卡点") == VISUAL_VIDEO
    assert _label_to_subtype("口播教学") == TALKING_VIDEO  # 含「口播」不含「非口播」
    assert _label_to_subtype("说不清") is None
    assert _label_to_subtype("") is None
