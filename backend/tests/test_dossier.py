"""博主档案:笔记池行构造/刷新、轨迹(基线/爆发/阶段/降级)、账号事实统计(纯函数,无 DB/LLM)。"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as N

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


def test_trajectory_detects_burst_and_phases():
    posts = [_post(i=i, like=1000 + (i % 3) * 100, days=i * 7) for i in range(1, 21)]
    posts.append(_post(i=99, like=18000, days=200))  # 爆发点:远超基线
    tr = build_trajectory(posts)
    assert any(b["like"] == 18000 for b in tr["bursts"])
    assert tr["phases"] and all(p["label"] in ("低谷期", "平稳期", "高位期") for p in tr["phases"])
    assert "爆发点" in tr["summary"]


def test_trajectory_flat_has_no_burst():
    tr = build_trajectory([_post(i=i, like=1000, days=i * 3) for i in range(1, 16)])
    assert tr["bursts"] == []


# ============================ stats ============================

def test_account_stats_counts_and_engagement():
    posts = [_post(i=1, view=1000, like=100, fav=50, com=10, level="full"), _post(i=2, view=0, level="list", days=3)]
    st = account_stats(posts)
    assert st["note_count"] == 2 and st["full_count"] == 1 and st["list_count"] == 1
    assert st["engagement_rate"] == round(160 / 1000, 4)  # 仅有浏览量的那篇参与互动率
    assert "frequency_info" in st and "growth_trend" in st  # 账号事实在档案层,不在蒸馏 stats


def test_account_stats_empty():
    assert account_stats([]) == {"note_count": 0}
