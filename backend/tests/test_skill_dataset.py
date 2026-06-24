from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.skill_optimization.dataset import main_modality, split_notes

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _post(i, subtype="image_text", title=None, body="正文内容这里", transcript=""):
    return SimpleNamespace(
        id=i,
        title=title if title is not None else f"标题{i}",
        body_text=body,
        transcript_text=transcript,
        content_subtype=subtype,
        published_at=BASE + timedelta(days=i),
    )


def test_main_modality_majority():
    posts = [_post(i, "image_text") for i in range(5)] + [_post(99, "talking_video")]
    assert main_modality(posts) == "image_text"


def test_split_is_time_ordered_and_holds_out_newest():
    posts = [_post(i) for i in range(12)]  # day0..day11
    res = split_notes(posts, min_total=12)
    # 最新的应在 test,最旧的在 train
    assert res.test[-1].id == 11
    assert res.train[0].id == 0
    # train 全早于 val、val 全早于 test
    assert max(s.id for s in res.train) < min(s.id for s in res.val)
    assert max(s.id for s in res.val) < min(s.id for s in res.test)
    assert len(res.train) + len(res.val) + len(res.test) == 12


def test_min_total_enforced():
    with pytest.raises(ValueError):
        split_notes([_post(i) for i in range(5)], min_total=12)


def test_minority_modality_dropped_and_counted():
    posts = [_post(i, "image_text") for i in range(12)] + [_post(50, "talking_video")]
    res = split_notes(posts, min_total=12)
    assert res.main_modality == "image_text"
    assert res.dropped_minority == 1
    assert res.total_kept == 12


def test_video_modality_uses_transcript_gold():
    posts = [
        _post(i, "talking_video", body="", transcript=f"大家好[0:0.0,1:0.2]这是第{i}条口播内容")
        for i in range(12)
    ]
    res = split_notes(posts, min_total=12)
    assert res.main_modality == "talking_video"
    assert all("[0:0.0" not in s.gold and s.gold for s in res.train + res.val + res.test)
