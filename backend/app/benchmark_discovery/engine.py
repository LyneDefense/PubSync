"""对标发现「评分」侧已下线,仅保留搜索页速览用的火爆度公式(纯规则,不调 LLM)。"""

from __future__ import annotations

import math
import statistics


def popularity_score(follower_count: int, like_samples: list[int]) -> float:
    """火爆度(0-100)= 0.5·粉丝分 + 0.5·互动分。搜索结果的 quick_popularity 速览用。"""
    follower = max(int(follower_count or 0), 0)
    follower_score = min(100.0, 20.0 * math.log10(follower + 1))  # 1k≈60 / 1w≈80 / 10w≈100
    likes = [int(x) for x in like_samples if x and int(x) > 0]
    if likes and follower > 0:
        rate = statistics.median(likes) / follower
        engagement_score = min(100.0, rate / 0.05 * 100.0)  # 互动率 5% 封顶满分
    elif likes:
        engagement_score = min(100.0, 20.0 * math.log10(statistics.median(likes) + 1))
    else:
        engagement_score = follower_score  # 无互动数据,退回粉丝分
    return round(0.5 * follower_score + 0.5 * engagement_score, 1)
