"""video_frames 纯函数:场景时间解析 / 节奏计算 / 代表帧时间点选取。ffmpeg IO 不在此测。"""

from app.blogger_distillation.video_frames import (
    compute_pacing,
    parse_scene_times,
    pick_frame_timestamps,
)


def test_parse_scene_times_dedup_sorted():
    stderr = "x pts_time:3.0 y\nfoo pts_time:1.5 bar\nz pts_time:3.0\n no match here\n"
    assert parse_scene_times(stderr) == [1.5, 3.0]
    assert parse_scene_times("") == []


def test_compute_pacing_fast():
    p = compute_pacing([1.0, 2.0, 3.0], 8.0, fast_cpm=20.0, slow_cpm=6.0)
    assert p["shot_count"] == 4  # 3 切换 → 4 镜头
    assert p["avg_shot_s"] == 2.0
    assert p["cuts_per_min"] == 30.0
    assert p["pace"] == "fast"


def test_compute_pacing_slow_and_no_duration():
    assert compute_pacing([], 60.0, fast_cpm=20.0, slow_cpm=6.0)["pace"] == "slow"  # 1 镜头/分 → 慢
    # 无时长:只有镜头数,无节奏字段。
    p = compute_pacing([1.0], None, fast_cpm=20.0, slow_cpm=6.0)
    assert p == {"shot_count": 2}


def test_pick_frame_timestamps_midpoints():
    # 3 切换 → 4 镜头,取 4 个中点。
    assert pick_frame_timestamps([2.0, 4.0, 6.0], 8.0, cap=10) == [1.0, 3.0, 5.0, 7.0]


def test_pick_frame_timestamps_capped():
    scenes = [float(i) for i in range(1, 20)]  # 19 切换 → 20 镜头
    picked = pick_frame_timestamps(scenes, 20.0, cap=5)
    assert len(picked) == 5
    assert picked == sorted(picked)


def test_pick_frame_timestamps_no_duration():
    assert pick_frame_timestamps([1.0, 2.0], None, cap=5) == []
