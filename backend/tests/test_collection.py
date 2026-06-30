import pytest

from app.blogger_distillation.service.collection import select_targets
from app.blogger_distillation.service.extract.post import normalize_post
from app.blogger_distillation.tikhub_client import XhsPostCandidate
from app.blogger_distillation.tikhub_client.base import TikHubError
from app.blogger_distillation.tikhub_client.parsers import parse_xhs_note_link


def _cand(ext: str, likes: int) -> XhsPostCandidate:
    return XhsPostCandidate(
        external_id=ext, xsec_token="t", note_type="image", like_count=likes,
        favorite_count=0, comment_count=0, share_count=0, raw={},
    )


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


def test_normalize_post_image_note_list_shape():
    # app/get_note_info 的真实壳:正文在 data.data[0].note_list[0].desc。
    # 回归前这层 note_list 壳没被识别,导致图文 body_text 全空。
    detail = {"data": {"data": [{"note_list": [{"desc": "图文正文内容", "title": "图文标题"}]}]}}
    out = normalize_post(_cand("img1", 10), detail)
    assert out["body_text"] == "图文正文内容"
    assert out["title"] == "图文标题"
    assert out["content_type"] == "image"


def test_normalize_post_note_list_directly_under_data():
    detail = {"data": {"note_list": [{"desc": "另一种壳的正文"}]}}
    out = normalize_post(_cand("img2", 10), detail)
    assert out["body_text"] == "另一种壳的正文"


def test_normalize_post_notecard_shape_still_works():
    # 既有 noteCard 壳(app_v2 / web_v3)不能因修复而回归。
    detail = {"data": {"noteCard": {"desc": "卡片正文", "title": "卡片标题"}}}
    out = normalize_post(_cand("nc1", 10), detail)
    assert out["body_text"] == "卡片正文"
    assert out["title"] == "卡片标题"


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
