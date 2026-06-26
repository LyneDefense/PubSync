"""博主诊断·硬实力纯函数单测。"""

from datetime import datetime, timedelta, timezone

from app.appraisal.hard import (
    AccountStat,
    PostStat,
    _interp,
    hard_dimensions,
    score_activity,
    score_like_collect_ratio,
    score_reach,
    score_viral,
)
from app.appraisal.judge import judge_soft, judge_vertical

NOW = datetime(2026, 6, 26, tzinfo=timezone.utc)


def test_interp_clamps_and_interpolates():
    pts = [(0, 0), (1.5, 75), (3, 100)]
    assert _interp(-1, pts) == 0
    assert _interp(10, pts) == 100
    assert _interp(1.5, pts) == 75
    assert _interp(0.75, pts) == 37.5  # 中点


def test_reach_log_scale():
    assert score_reach(AccountStat(follower_count=1000)).score == 75
    assert score_reach(AccountStat(follower_count=100)).score == 50
    assert score_reach(AccountStat(follower_count=0)).score == 0
    assert score_reach(AccountStat(follower_count=10_000_000)).score == 100  # clamp
    assert "头部" in score_reach(AccountStat(follower_count=200_000)).detail


def test_like_collect_ratio_anchors():
    assert score_like_collect_ratio(AccountStat(follower_count=100, total_like_collect=150)).score == 75  # 1.5
    assert score_like_collect_ratio(AccountStat(follower_count=100, total_like_collect=300)).score == 100  # 3.0
    assert score_like_collect_ratio(AccountStat(follower_count=100, total_like_collect=50)).score == 40  # 0.5


def test_ces_weights_comments_higher():
    p = PostStat(likes=10, collects=5, comments=2)
    assert p.ces == 10 + 5 + 2 * 4  # 23


def test_viral_detects_outlier_and_handles_empty():
    posts = [PostStat(likes=100) for _ in range(9)] + [PostStat(likes=1000)]
    dim = score_viral(posts)
    assert abs(dim.metric["hot_rate"] - 0.1) < 0.01  # 1/10 笔记是爆文
    assert dim.metric["ces_median"] == 100
    assert dim.score > 30
    assert score_viral([]).score == 0


def test_activity_frequency_and_recency():
    # 近 90 天里 ~40 篇(约 3.5 篇/周)、最近刚更 → 分高
    fresh = [PostStat(published_at=NOW - timedelta(days=i * 2)) for i in range(40)]
    assert score_activity(fresh, NOW).score >= 60
    # 同样篇数但最后一篇在 100 天前 → recency 惩罚,分低
    stale = [PostStat(published_at=NOW - timedelta(days=100 + i * 7)) for i in range(12)]
    assert score_activity(stale, NOW).score < 40
    # 没有发布时间 → 0
    assert score_activity([PostStat(likes=5)], NOW).score == 0


def test_hard_dimensions_returns_four():
    dims = hard_dimensions(
        AccountStat(follower_count=5000, total_like_collect=12000),
        [PostStat(likes=200, collects=50, comments=10, published_at=NOW - timedelta(days=3))],
        NOW,
    )
    assert [d.key for d in dims] == ["reach", "engagement", "viral", "activity"]
    assert all(0 <= d.score <= 100 for d in dims)


# —— 软实力 / 垂直度(模型判,monkeypatch 掉 LLM)——

def test_judge_vertical_parses(monkeypatch):
    monkeypatch.setattr("app.appraisal.judge.create_json_response",
                        lambda *a, **k: {"score": 90, "niche": "香港保险", "reason": "全是港险科普"})
    dim = judge_vertical(["香港保险攻略", "储蓄险测评"], settings=None)
    assert dim.score == 90 and dim.extra["niche"] == "香港保险"


def test_judge_vertical_fallback_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("llm down")
    monkeypatch.setattr("app.appraisal.judge.create_json_response", boom)
    assert judge_vertical(["x"], settings=None).score == 50


def test_judge_soft_parses_three_dims(monkeypatch):
    canned = {
        "intent_facets": {"题材": "保险", "形态": "科普", "调性": "涨粉IP"},
        "account_facets": {"题材": "保险", "形态": "科普", "调性": "销售"},
        "对路": {"score": 80, "reason": "题材形态匹配,调性偏销售", "题材匹配": True, "形态匹配": True, "调性匹配": False},
        "可学": {"score": 70, "reason": "选题需求驱动"},
        "可蒸馏": {"score": 60, "reason": "代表作够清晰"},
    }
    monkeypatch.setattr("app.appraisal.judge.create_json_response", lambda *a, **k: canned)
    dims = judge_soft("想学把保险讲专业", "标题1\n标题2", settings=None)
    assert dims["fit"].score == 80 and dims["learnable"].score == 70 and dims["distillable"].score == 60
    assert dims["fit"].extra["facet_match"]["调性匹配"] is False


def test_judge_soft_fallback_on_empty_intent():
    dims = judge_soft("", "notes", settings=None)
    assert all(d.score == 50 for d in dims.values())
