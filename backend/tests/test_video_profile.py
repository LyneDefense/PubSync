"""视频档案 L0 派生:derive_narration_level / assemble_video_profile_l0 / derive_video_tags。纯函数,零 LLM。"""

from app.blogger_distillation.modality import (
    assemble_video_profile_l0,
    derive_narration_level,
    derive_video_tags,
)


def test_narration_level_by_density():
    # 有时长走字·秒:高密度=口播为主,低密度=少量口播,中间=半口播。
    assert derive_narration_level("字" * 360, 60, density_high_cps=3.0, density_low_cps=1.0) == "high"  # 6 cps
    assert derive_narration_level("字" * 30, 60, density_high_cps=3.0, density_low_cps=1.0) == "low"   # 0.5 cps
    assert derive_narration_level("字" * 120, 60, density_high_cps=3.0, density_low_cps=1.0) == "mid"  # 2 cps


def test_narration_level_no_transcript_or_duration():
    assert derive_narration_level("", 60) == "none"
    # 无时长走字数回退。
    assert derive_narration_level("字" * 250, None, min_transcript_chars=200) == "mid"
    assert derive_narration_level("短", None, min_transcript_chars=200) == "low"


def test_profile_l0_image_is_empty():
    assert assemble_video_profile_l0("image", "任何", 12) == {}


def test_profile_l0_video_fields():
    p = assemble_video_profile_l0("video", "字" * 300, 100, density_high_cps=3.0, density_low_cps=1.0)
    assert p["layer"] == "L0"
    assert p["transcript_len"] == 300
    assert p["duration_s"] == 100.0
    assert p["speech_cps"] == 3.0
    assert p["narration_level"] == "high"


def test_profile_l0_video_no_transcript():
    p = assemble_video_profile_l0("video", "", 40)
    assert p["narration_level"] == "none"
    assert "speech_cps" not in p  # 无转写不给密度


def test_derive_tags_layered():
    assert derive_video_tags({}) == {}
    assert derive_video_tags({"narration_level": "high"}) == {"narration_level": "high"}
    # L1/L2 字段在时一并派生。
    full = {"narration_level": "low", "pace": "fast", "on_camera": True}
    assert derive_video_tags(full) == {"narration_level": "low", "pace": "fast", "on_camera": True}
