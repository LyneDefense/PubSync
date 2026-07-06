"""博主档案:笔记池行构造/刷新、轨迹(基线/爆发/阶段/降级)、账号事实统计(纯函数,无 DB/LLM)。"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as N

from app.blogger_dossier.audience import _reader_comments, parse_audience
from app.blogger_dossier.habits import (
    _author_reply_habit,
    _comment_guide_ratio,
    _content_format,
    _genre_distribution,
    _hashtag_usage,
    _posting_time,
)
from app.blogger_dossier.pool import _new_list_row, refresh_from_candidate
from app.blogger_dossier.stats import account_stats
from app.blogger_dossier.trajectory import build_trajectory
from app.blogger_distillation.tikhub_client import XhsPostCandidate
from app.models import BloggerPost

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _cand(ext="n1", like=100, fav=50, com=10, view=1000, ts=_T0, token="tok1"):
    return XhsPostCandidate(
        external_id=ext, xsec_token=token, note_type="image",
        like_count=like, favorite_count=fav, comment_count=com, share_count=1,
        raw={"id": f"biz-{ext}", "display_title": f"标题{ext}"},
        published_at=ts, view_count=view,
    )


def _post(i=1, like=100, fav=50, com=10, view=1000, days=0, ct="image", level="list", status="active"):
    return N(
        id=i, external_id=f"n{i}", title=f"标题{i}", like_count=like, favorite_count=fav,
        comment_count=com, share_count=1, view_count=view, score=like * 0.35 + fav * 0.45,
        published_at=_T0 + timedelta(days=days), content_type=ct, detail_level=level, status=status,
    )


# ============================ pool ============================

def test_new_list_row_fields():
    row = _new_list_row(1, N(id=7, platform="xhs"), _cand(), "biz-n1")
    assert row.detail_level == "list" and row.note_key == "biz-n1"
    assert row.title == "标题n1" and row.published_at == _T0 and row.view_count == 1000
    assert row.xsec_token == "tok1" and row.asr_status == "not_required" and row.vision_status == "not_required"


def test_refresh_from_candidate_updates_without_downgrade():
    post = BloggerPost(
        tenant_id=1, blogger_id=7, external_id="n1", title="旧标题",
        like_count=10, favorite_count=5, comment_count=1, share_count=0,
        detail_level="full", xsec_token="old", published_at=None,
    )
    refresh_from_candidate(post, _cand(like=200, fav=80, com=20, view=5000, token="new"))
    assert post.like_count == 200 and post.view_count == 5000
    assert post.published_at == _T0  # 补时间
    assert post.xsec_token == "new"  # token 用最新
    assert post.detail_level == "full"  # 不降级
    assert post.last_seen_at is not None


def test_refresh_zero_counts_do_not_wipe():
    post = BloggerPost(tenant_id=1, blogger_id=7, external_id="n1", title="t", like_count=100, favorite_count=50)
    refresh_from_candidate(post, _cand(like=0, fav=0, com=0, view=0, ts=None, token=""))
    assert post.like_count == 100 and post.favorite_count == 50  # 0 不覆盖


# ============================ trajectory ============================

def test_trajectory_too_few_points_degrades_honestly():
    tr = build_trajectory([_post(i=i, days=i) for i in range(5)])
    assert tr["phases"] == [] and tr["bursts"] == []
    assert "暂不划分阶段" in tr["summary"]


_PHASE_LABELS = ("起步期", "突破期", "滑坡期", "成熟期", "平稳期")


def test_trajectory_detects_burst_and_phases():
    posts = [_post(i=i, like=1000 + (i % 3) * 100, days=i * 7) for i in range(1, 21)]
    posts.append(_post(i=99, like=18000, days=200))  # 爆发点:远超基线,但单篇不成台阶
    tr = build_trajectory(posts)
    assert any(b["like"] == 18000 for b in tr["bursts"])
    assert tr["phases"] and all(p["label"] in _PHASE_LABELS for p in tr["phases"])
    assert "爆发点" in tr["summary"]


def test_trajectory_flat_has_no_burst():
    tr = build_trajectory([_post(i=i, like=1000, days=i * 3) for i in range(1, 16)])
    assert tr["bursts"] == []


def test_trajectory_level_up_detects_growth_step():
    # 前段基线 ~800、后段 ~4000(持久台阶)→ 涨粉拐点 + 突破期,这是"赞藏替涨粉看台阶"的落地。
    early = [_post(i=i, like=800, days=i * 10) for i in range(1, 9)]
    late = [_post(i=100 + i, like=4000, days=210 + i * 10) for i in range(1, 9)]
    tr = build_trajectory(early + late)
    assert tr["level_ups"] and tr["level_ups"][0]["to_avg"] > tr["level_ups"][0]["from_avg"]
    assert any(p["label"] == "突破期" for p in tr["phases"])
    assert tr["level_ups"][0]["trigger"] is not None  # 关联触发爆文


def test_trajectory_distribution_and_bucket_percentiles():
    # 图B 表现分布 + 图A 分位带的数据:distribution 分位单调、log 分箱计数守恒;桶带 p25/p75。
    posts = [_post(i=i, like=500 + i * 200, days=i * 7) for i in range(1, 21)]
    tr = build_trajectory(posts)
    d = tr["distribution"]
    assert d["count"] == 20
    assert d["min"] <= d["p25"] <= d["median"] <= d["p75"] <= d["p90"] <= d["max"]
    assert d["log_bins"] and sum(b["count"] for b in d["log_bins"]) == 20
    assert all("p25" in b and "p75" in b for b in tr["buckets"])


def test_trajectory_distribution_present_even_when_degraded():
    tr = build_trajectory([_post(i=i, like=100 + i, days=i) for i in range(5)])  # < MIN_POINTS
    assert tr["distribution"]["count"] == 5  # 降级也给分布


# ============================ audience(受众需求·读者最常问) ============================

def test_audience_reader_comments_filters_and_sorts():
    posts = [
        N(comments_json=json.dumps([
            {"content": "这个多少钱啊", "like_count": 50, "is_author": False},
            {"content": "谢谢支持", "like_count": 5, "is_author": True},    # 博主回复→剔
            {"content": "适合新手吗", "like_count": 99, "is_author": False},
            {"content": "1", "like_count": 3, "is_author": False},          # 太短→剔
        ])),
        N(comments_json="not-json"),  # 坏 json 跳过
        N(comments_json=None),
    ]
    out = _reader_comments(posts)
    assert [c["text"] for c in out] == ["适合新手吗", "这个多少钱啊"]  # 热度降序,博主/短评剔除


def test_audience_parse_ignores_legacy_and_junk():
    assert parse_audience(json.dumps({"questions": [{"theme": "价格", "sample": "多少钱"}]})) is not None
    assert parse_audience(json.dumps({"hypotheses": []})) is None  # 旧归因形态 → 视为无
    assert parse_audience("") is None
    assert parse_audience("broken") is None


# ============================ stats ============================

def test_account_stats_counts():
    posts = [_post(i=1, view=1000, like=100, fav=50, com=10, level="full"), _post(i=2, view=0, level="list", days=3)]
    st = account_stats(posts)
    assert st["note_count"] == 2 and st["full_count"] == 1 and st["list_count"] == 1
    assert "engagement_rate" not in st  # 互动率已下线:小红书无浏览量,恒算不出
    assert st["favorite_like_ratio"] == round(50 / 100, 4)
    assert "frequency_info" in st and "growth_trend" in st  # 账号事实在档案层,不在蒸馏 stats


def test_account_stats_empty():
    assert account_stats([]) == {"note_count": 0}


# ============================ habits (运营习惯) ============================

def _dp(i=1, body="", title="", transcript="", comments=None):
    return N(id=i, detail_level="full", body_text=body, title=title, transcript_text=transcript,
             comments_json=json.dumps(comments or [], ensure_ascii=False))


def test_habits_listicle_needs_three_list_lines():
    listy = _dp(body="1. 一\n2. 二\n3. 三\n随便一句")
    plain = _dp(body="就是一段普通正文，没有列表。")
    g = _genre_distribution([listy, plain])
    assert g["listicle"] == 1 and g["total"] == 2 and g["ratio"] == 0.5


def test_habits_comment_guide_reads_author_content():
    guided = _dp(title="干货来了", body="有需要的扣1，评论区告诉我")
    silent = _dp(title="随手记", body="今天天气不错")
    cg = _comment_guide_ratio([guided, silent])
    assert cg["count"] == 1 and cg["total"] == 2


def test_habits_author_reply_ignores_reader_comments():
    # 「帮我看看号吗」是读者评论(is_author=False),绝不能当成博主的运营习惯。
    replied = _dp(comments=[{"content": "谢谢", "is_author": True}, {"content": "帮我看看号吗", "is_author": False}])
    reader_only = _dp(comments=[{"content": "帮我看看号吗", "is_author": False}])
    ar = _author_reply_habit([replied, reader_only])
    assert ar["with_comments"] == 2 and ar["replied"] == 1 and ar["ratio"] == 0.5


def test_habits_posting_time_beijing():
    # UTC 13:00 周一 → 北京 21:00 周一(晚间)。2024-01-01 是周一。
    posts = [N(published_at=datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc), content_type="image") for _ in range(5)]
    pt = _posting_time(posts)
    assert pt["sample"] == 5 and sum(pt["weekday_counts"]) == 5
    assert pt["top_weekday"] == "一" and pt["top_band"] == "晚间"


def test_habits_posting_time_too_few_degrades():
    pt = _posting_time([N(published_at=None, content_type="image")])
    assert pt["top_weekday"] is None and pt["weekday_counts"] == []


def test_habits_hashtag_usage():
    detail = [
        N(hashtags_json='["#香港保险", "储蓄险"]'),
        N(hashtags_json='["香港保险"]'),
        N(hashtags_json="[]"),
    ]
    h = _hashtag_usage(detail)
    assert h["avg_per_note"] == 1.0 and h["notes_with"] == 2  # (2+1+0)/3
    assert h["top_tags"][0] == {"tag": "香港保险", "count": 2}  # # 前缀已剥


def test_habits_content_format():
    posts = [
        N(content_type="image", vision_image_count=8, media_urls_json="[]", duration_seconds=None),
        N(content_type="image", vision_image_count=0, media_urls_json='["a", "b", "c", "d"]', duration_seconds=None),
        N(content_type="video", vision_image_count=0, media_urls_json="[]", duration_seconds=60.0),
    ]
    f = _content_format(posts)
    assert f["avg_images"] == 6.0 and f["image_notes"] == 2  # (8+4)/2
    assert f["avg_video_sec"] == 60 and f["video_notes"] == 1


# ============================ compliance (合规体检) ============================

def test_compliance_scan_pool_reports_coverage():
    from app.blogger_dossier.compliance import scan_pool
    posts = [N(title="普通标题", body_text="正文内容", detail_level="full"),
             N(title="列表级标题", body_text="", detail_level="list")]
    rep = scan_pool("xhs", "美妆", ["护肤"], posts)
    assert rep["coverage"] == {"pool": 2, "title_level": 2, "full_text": 1}
    assert "grade" in rep and "hits" in rep
