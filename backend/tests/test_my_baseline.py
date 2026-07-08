"""我的账号拍法基线汇总(纯函数):从视频 video_profile 算基线 + 渲染成 prompt 一句话。"""

from app.xhs_creation.my_baseline import render_baseline_line, summarize_video_baseline


def test_summarize_empty():
    assert summarize_video_baseline([]) == {}
    assert summarize_video_baseline([{}, None]) == {}


def test_summarize_median_shots_and_dominant_pace():
    profiles = [
        {"shot_count": 4, "pace": "fast", "narration_level": "high", "on_camera": True, "shot_style": "怼脸口播"},
        {"shot_count": 6, "pace": "fast", "narration_level": "high", "on_camera": True},
        {"shot_count": 20, "pace": "slow", "narration_level": "mid", "on_camera": False},
    ]
    b = summarize_video_baseline(profiles)
    assert b["sample_count"] == 3
    assert b["median_shot_count"] == 6         # 中位数(非平均,抗离群)
    assert b["pace"] == "fast"                 # 主导节奏
    assert b["narration_level"] == "high"
    assert b["on_camera"] is True              # 过半出镜
    assert "怼脸口播" in b["shot_styles"]


def test_summarize_l0_only_degrades_to_narration():
    # 只有 L0(口播浓度),没有镜头/节奏/出镜 → 基线只带 narration,其余键缺省。
    b = summarize_video_baseline([{"narration_level": "high"}, {"narration_level": "high"}])
    assert b["narration_level"] == "high"
    assert "median_shot_count" not in b and "pace" not in b and "on_camera" not in b


def test_summarize_on_camera_minority_is_false():
    # 出镜占比未过半 → 记「画外音」。
    b = summarize_video_baseline([{"on_camera": True}, {"on_camera": False}, {"on_camera": False}])
    assert b["on_camera"] is False


def test_render_line_empty():
    assert render_baseline_line({}) == ""
    assert render_baseline_line({"sample_count": 0}) == ""  # 无任何可读维度


def test_render_line_human_readable():
    line = render_baseline_line(
        {"sample_count": 3, "median_shot_count": 6, "pace": "fast", "narration_level": "high", "on_camera": True}
    )
    assert "3 条" in line and "6 个镜头" in line and "快节奏" in line and "口播为主" in line and "出镜" in line
