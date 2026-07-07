"""火爆度公式(搜索页 quick_popularity 速览)单测。推荐/评分整套已下线。"""

from app.benchmark_discovery.engine import popularity_score


def test_popularity_follower_tiers():
    assert popularity_score(0, []) == 0.0
    assert 55 <= popularity_score(1000, []) <= 65  # 无互动 → 退回粉丝分(~60)
    assert popularity_score(100000, []) >= 95


def test_popularity_engagement_caps_at_5pct():
    # 互动率 5% 封顶满分,叠加粉丝分
    high = popularity_score(10000, [500, 500, 500])
    low = popularity_score(10000, [10, 10, 10])
    assert high > low


def test_popularity_no_likes_falls_back_to_follower():
    assert popularity_score(10000, []) == popularity_score(10000, [0, 0])
