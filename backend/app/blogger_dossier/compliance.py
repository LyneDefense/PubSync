"""合规体检(账号事实):对博主全量池,按**博主自己的赛道**扫广告法红线。

定位是**模仿链路的护栏**——你要从这个博主蒸馏 skill 照着做,他若靠极限词/绝对化博眼球,
蒸出的 skill 会继承;档案先亮红灯。赛道用博主自身 niche/tags/标题识别(不叠加用户品类,
那是对标分析的事)。标题级覆盖全量池、正文级只覆盖详情级——如实标覆盖度。P1 纯规则,不花钱、不调 LLM。
"""

from __future__ import annotations

from typing import Any

from app.compliance import scan_account
from app.models import BloggerPost


def scan_pool(platform: str, niche: str, tags: list[str], posts: list[BloggerPost]) -> dict[str, Any]:
    """扫全量池,返回 to_report_dict() + 覆盖度。空池返回 {}。"""
    if not posts:
        return {}
    titles = [p.title or "" for p in posts]
    # 只看博主自身内容:标题(全量池都有)+ 正文(仅详情级)。
    texts = [f"{p.title or ''}\n{p.body_text or ''}".strip() for p in posts]
    result = scan_account(texts, platform, niche=niche, tags=tags, titles=titles)
    report = result.to_report_dict()
    report["coverage"] = {
        "pool": len(posts),
        "title_level": len(posts),
        "full_text": sum(1 for p in posts if p.detail_level == "full"),
    }
    return report
