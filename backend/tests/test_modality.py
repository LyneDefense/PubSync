from app.blogger_distillation import analysis
from app.blogger_distillation.modality import (
    IMAGE_TEXT,
    TALKING_VIDEO,
    UNKNOWN,
    VISUAL_VIDEO,
    classify_subtype,
    coarse_modality,
)
from app.models import BloggerPost


def _post(**kw) -> BloggerPost:
    defaults = dict(
        tenant_id=1,
        blogger_id=1,
        external_id="x",
        title="标题",
        body_text="",
        content_type="image",
        content_subtype="image_text",
        transcript_text="",
        like_count=0,
        favorite_count=0,
        comment_count=0,
        share_count=0,
        score=0.0,
    )
    defaults.update(kw)
    return BloggerPost(**defaults)


def test_classify_subtype():
    assert classify_subtype("image", "", min_transcript_chars=200) == IMAGE_TEXT
    assert classify_subtype("video", "字" * 250, min_transcript_chars=200) == TALKING_VIDEO
    assert classify_subtype("video", "太短了", min_transcript_chars=200) == VISUAL_VIDEO
    assert classify_subtype("video", "", min_transcript_chars=200) == UNKNOWN


def test_coarse_modality():
    assert coarse_modality("video") == "video"
    assert coarse_modality("image") == "image"


def test_analyze_by_modality_separates_scales():
    posts = [
        _post(content_type="image", content_subtype="image_text", like_count=100, favorite_count=50, score=100),
        _post(content_type="image", content_subtype="image_text", like_count=200, favorite_count=80, score=200),
        _post(content_type="video", content_subtype="talking_video", like_count=5000, favorite_count=1000, score=5000),
        _post(content_type="video", content_subtype="talking_video", like_count=9000, favorite_count=2000, score=9000),
    ]
    stats = analysis.analyze_posts(posts)
    by_modality = stats["by_modality"]
    # 视频与图文均值分开算,不被对方量级带偏。
    assert by_modality["image"]["count"] == 2
    assert by_modality["video"]["count"] == 2
    assert by_modality["image"]["average_like"] == 150
    assert by_modality["video"]["average_like"] == 7000
    assert stats["subtype_counts"]["image_text"] == 2
    assert stats["subtype_counts"]["talking_video"] == 2
    assert "显著高于" in stats["modality_comparison"]


def test_hot_ranking_is_within_modality():
    # 图文量级远小于视频;模态内排序应让图文的 top 也能进 hot,不被视频垄断。
    posts = [
        _post(content_type="image", content_subtype="image_text", like_count=10, score=10),
        _post(content_type="image", content_subtype="image_text", like_count=300, score=300),
        _post(content_type="video", content_subtype="talking_video", like_count=8000, score=8000),
        _post(content_type="video", content_subtype="talking_video", like_count=9000, score=9000),
        _post(content_type="video", content_subtype="talking_video", like_count=9500, score=9500),
    ]
    pct = analysis._percentile_within_modality(posts)
    # 每个模态各自的最高分百分位都是 1.0(同模态内 top)。
    top_image = max((p for p in posts if p.content_type == "image"), key=lambda p: p.score)
    top_video = max((p for p in posts if p.content_type == "video"), key=lambda p: p.score)
    assert pct[id(top_image)] == 1.0
    assert pct[id(top_video)] == 1.0
