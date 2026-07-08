"""拍法渲染:evidence._motion_line(证据块)+ post_content.motion_context(可学文本)。纯字符串,无 LLM。"""

from types import SimpleNamespace as N

from app.blogger_distillation.evidence import _motion_line
from app.blogger_distillation.post_content import motion_context

_PROFILE = {
    "layer": "L2", "shot_count": 42, "cuts_per_min": 28.0, "pace": "fast",
    "on_camera": True, "hook_3s": "怼脸抛问题", "shot_style": "近景为主",
    "on_screen_text": "全程大字幕", "transitions": "硬切快剪", "style_summary": "快节奏出镜口播",
}


def test_evidence_motion_line():
    line = _motion_line({"video_profile": _PROFILE})
    assert line.startswith("  视频拍法：")
    assert "42个镜头" in line and "28.0cuts/min" in line and "快剪" in line and "出镜" in line
    assert "怼脸抛问题" in line and "快节奏出镜口播" in line
    # 无档案 → 空串
    assert _motion_line({"video_profile": {}}) == ""
    assert _motion_line({}) == ""


def test_post_content_motion_context():
    import json
    ctx = motion_context(N(video_profile=json.dumps(_PROFILE)))
    assert "节奏：42个镜头、28.0 cuts/min、快剪" in ctx
    assert "出镜：真人对镜口播" in ctx
    assert "开头3秒：怼脸抛问题" in ctx and "拍法概括：快节奏出镜口播" in ctx
    # 无 / 坏数据 → 空串
    assert motion_context(N(video_profile="")) == ""
    assert motion_context(N(video_profile="not json")) == ""
