"""创作产物归一化:分镜脚本保留拍法字段(景别/钩子/节奏),丢弃噪声键。"""

from app.xhs_creation.normalize import normalize_script


def test_normalize_video_script_keeps_shot_fields():
    raw = {
        "duration_seconds": 30,
        "hook": " 开头怼脸提问 ",
        "pacing": "镜头偏快",
        "segments": [
            {"start": "0s", "end": "3s", "shot_type": "近景怼脸", "scene": "对镜提问", "voiceover": "你也这样?", "subtitle": "共鸣", "junk": "x"},
        ],
        "shooting_notes": [" 手机固定机位 ", ""],
    }
    out = normalize_script(raw, "video_script")
    assert out["hook"] == "开头怼脸提问"       # 去空白
    assert out["pacing"] == "镜头偏快"
    seg = out["segments"][0]
    assert seg["shot_type"] == "近景怼脸" and seg["scene"] == "对镜提问"
    assert "junk" not in seg                    # 噪声键丢弃
    assert out["shooting_notes"] == ["手机固定机位"]  # 空串滤掉


def test_normalize_spoken_script_keeps_hook():
    out = normalize_script({"hook": "第一句抓人", "segments": [{"voiceover": "开场"}]}, "spoken_script")
    assert out["hook"] == "第一句抓人"
    assert out["segments"][0]["voiceover"] == "开场"


def test_normalize_non_script_type_unchanged():
    assert normalize_script({"segments": []}, "image_note") == {}


def test_normalize_missing_script_gives_empty_lists():
    out = normalize_script(None, "spoken_script")
    assert out["segments"] == [] and out["shooting_notes"] == [] and out["hook"] == ""
