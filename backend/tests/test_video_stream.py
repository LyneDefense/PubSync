from app.blogger_distillation.service.extract import (
    extract_video_url,
    is_mostly_chinese,
    pick_video_stream,
    strip_asr_timestamps,
    to_https,
)


def test_is_mostly_chinese():
    assert is_mostly_chinese("如果你也对现在的工作不满意，想辞职") is True
    assert is_mostly_chinese("If I had understood these truths in my twenties") is False
    assert is_mostly_chinese("") is False
    # 中英混排但中文为主仍算中文
    assert is_mostly_chinese("我在菲律宾 CPI 语言学校学了两周") is True


def test_strip_asr_timestamps():
    raw = "[0:0.000,1:0.220] 这是一个反人性的习惯[1:0.220,2:1.500] 帮助我逆袭"
    assert strip_asr_timestamps(raw) == "这是一个反人性的习惯帮助我逆袭"
    assert strip_asr_timestamps("没有时间戳的文本") == "没有时间戳的文本"


def _raw_with_streams():
    # 同一视频两档同清晰度码流:h264 更大、h265 更小;地址都是 http(应被升到 https)。
    return {
        "video": {
            "media": {
                "stream": {
                    "h264": [
                        {
                            "masterUrl": "http://sns-v8.rednotecdn.com/a_258.mp4",
                            "size": 15963573,
                            "videoBitrate": 579397,
                            "width": 720,
                            "height": 1280,
                        }
                    ],
                    "h265": [
                        {
                            "masterUrl": "http://sns-v8.rednotecdn.com/a_513.mp4",
                            "size": 11686199,
                            "videoBitrate": 404613,
                            "width": 720,
                            "height": 1280,
                        }
                    ],
                }
            }
        }
    }


def test_to_https():
    assert to_https("http://x.com/a.mp4") == "https://x.com/a.mp4"
    assert to_https("https://x.com/a.mp4") == "https://x.com/a.mp4"
    assert to_https("") == ""


def test_pick_video_stream_prefers_smallest_h265_https():
    best = pick_video_stream(_raw_with_streams())
    assert best is not None
    assert best["codec"] == "h265"
    assert best["size"] == 11686199
    assert best["url"] == "https://sns-v8.rednotecdn.com/a_513.mp4"


def test_extract_video_url_uses_smallest_and_https():
    url = extract_video_url(_raw_with_streams())
    assert url == "https://sns-v8.rednotecdn.com/a_513.mp4"


def test_pick_video_stream_falls_back_to_backup_url():
    raw = {
        "video": {
            "stream": {
                "h264": [
                    {
                        "backupUrls": ["http://backup.rednotecdn.com/b_258.mp4"],
                        "size": 9000000,
                        "videoBitrate": 300000,
                    }
                ]
            }
        }
    }
    best = pick_video_stream(raw)
    assert best is not None
    assert best["url"] == "https://backup.rednotecdn.com/b_258.mp4"


def test_pick_video_stream_none_when_no_stream():
    assert pick_video_stream({"video": {}}) is None
    assert pick_video_stream({}) is None


def test_pick_video_stream_no_size_still_returns():
    # 无 size 字段时不应崩,仍能选出一个(按码率/编码偏好)。
    raw = {
        "video": {
            "stream": {
                "h264": [{"masterUrl": "http://x.com/h264.mp4"}],
                "h265": [{"masterUrl": "http://x.com/h265.mp4"}],
            }
        }
    }
    best = pick_video_stream(raw)
    assert best is not None
    # 都无 size 无码率时,按编码偏好 h265 优先。
    assert best["codec"] == "h265"
    assert best["url"] == "https://x.com/h265.mp4"
