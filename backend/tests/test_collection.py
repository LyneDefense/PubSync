import pytest

from app.blogger_distillation.service.collection import candidate_pool_depth, select_targets
from app.blogger_distillation.tikhub_client import XhsPostCandidate
from app.blogger_distillation.tikhub_client.base import TikHubError
from app.blogger_distillation.tikhub_client.parsers import parse_xhs_note_link
from app.config import Settings


def _settings() -> Settings:
    return Settings(auth_secret="unit-test-secret")


def _cand(ext: str, likes: int) -> XhsPostCandidate:
    return XhsPostCandidate(
        external_id=ext, xsec_token="t", note_type="image", like_count=likes,
        favorite_count=0, comment_count=0, share_count=0, raw={},
    )


def test_candidate_pool_depth_clamps():
    s = _settings()
    assert candidate_pool_depth(s, 10, False) == 100   # floor
    assert candidate_pool_depth(s, 50, False) == 250   # 50*5
    assert candidate_pool_depth(s, 80, False) == 300   # cap (400→300)
    assert candidate_pool_depth(s, 50, True) == 300    # fetch_all → cap


def test_select_targets_top_liked():
    pool = [_cand("a", 10), _cand("b", 500), _cand("c", 100)]
    picked = select_targets(pool, "top_liked", False, 2)
    assert [c.external_id for c in picked] == ["b", "c"]


def test_select_targets_latest_keeps_order():
    pool = [_cand("a", 10), _cand("b", 500), _cand("c", 100)]
    picked = select_targets(pool, "latest", False, 2)
    assert [c.external_id for c in picked] == ["a", "b"]


def test_select_targets_fetch_all():
    pool = [_cand("a", 10), _cand("b", 500)]
    assert len(select_targets(pool, "top_liked", True, 1)) == 2


def test_parse_xhs_note_link_explore():
    out = parse_xhs_note_link("https://www.xiaohongshu.com/explore/64abc?xsec_token=XYZ&xsec_source=pc")
    assert out == {"note_id": "64abc", "xsec_token": "XYZ"}


def test_parse_xhs_note_link_discovery_and_wrapped_text():
    out = parse_xhs_note_link("看看这个 https://www.xiaohongshu.com/discovery/item/9981?xsec_token=AA 超赞")
    assert out["note_id"] == "9981"
    assert out["xsec_token"] == "AA"


def test_parse_xhs_note_link_invalid():
    with pytest.raises(TikHubError):
        parse_xhs_note_link("https://www.xiaohongshu.com/user/profile/123")
