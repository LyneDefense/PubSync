"""运营习惯(账号事实模块):从全量池算的"博主怎么运营"行为统计。

事实主体在此(客观、随池重算、与选哪份画像无关);蒸馏层的解读由前端从画像 report 合并附加。
需正文/转写的项(体裁、评论引导)只对详情级笔记算,并给覆盖度,不拿列表级凑数。
评论引导只看**博主自身内容**(标题/正文/口播),不看读者评论;博主回复习惯才看评论里的 is_author。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.blogger_distillation.analysis import analyze_by_modality, modality_comparison
from app.blogger_dossier.stats import analyze_posting_frequency
from app.models import BloggerPost

# 清单体:正文里成排的序号/项目符号行。≥3 行即认为清单体。
_LIST_LINE = re.compile(r"^\s*(?:[0-9]{1,2}[.、)）:：]|[①-⑳]|[-•·▪✦●])")
# 博主主动引导互动的话术(出现在博主自己的标题/正文/口播里)。
_GUIDE_PHRASES = (
    "评论区", "扣1", "扣个1", "扣一个", "扣0", "留言告诉我", "评论告诉我", "评论区聊", "评论区见",
    "你怎么看", "你觉得呢", "说说你", "聊聊你", "求点赞", "求关注", "求收藏", "蹲一个", "在线等",
    "评论区扣", "评论区留言", "有需要的扣", "想要的扣",
)


def operating_habits(posts: list[BloggerPost]) -> dict[str, Any]:
    """运营习惯五面:发布节奏 / 模态偏好 / 体裁分布 / 评论引导 / 博主回复习惯。"""
    if not posts:
        return {}
    detail = [p for p in posts if p.detail_level == "full"]
    return {
        "coverage": {"pool": len(posts), "detail": len(detail)},
        "posting_rhythm": analyze_posting_frequency(posts),
        "modality_pref": modality_comparison(analyze_by_modality(posts)),
        "genre": _genre_distribution(detail),
        "comment_guide": _comment_guide_ratio(detail),
        "author_reply": _author_reply_habit(detail),
    }


def _is_listicle(body: str) -> bool:
    hits = sum(1 for line in (body or "").splitlines() if _LIST_LINE.match(line))
    return hits >= 3


def _genre_distribution(detail: list[BloggerPost]) -> dict[str, Any]:
    """体裁:清单体占比(需正文,仅详情级)。"""
    if not detail:
        return {"listicle": 0, "total": 0, "ratio": None}
    listicle = sum(1 for p in detail if _is_listicle(p.body_text or ""))
    return {"listicle": listicle, "total": len(detail), "ratio": round(listicle / len(detail), 3)}


def _comment_guide_ratio(detail: list[BloggerPost]) -> dict[str, Any]:
    """评论引导:博主**自身内容**(标题+正文+口播)里主动引导互动的笔记占比。不看读者评论。"""
    if not detail:
        return {"count": 0, "total": 0, "ratio": None}
    count = 0
    for p in detail:
        text = f"{p.title or ''}\n{p.body_text or ''}\n{p.transcript_text or ''}"
        if any(phrase in text for phrase in _GUIDE_PHRASES):
            count += 1
    return {"count": count, "total": len(detail), "ratio": round(count / len(detail), 3)}


def _author_reply_habit(detail: list[BloggerPost]) -> dict[str, Any]:
    """博主回复习惯:有评论的笔记里,博主本人下场回复的占比(靠评论 is_author)。

    存量评论无 is_author 标记 → 只统计新采到的;replied 恒 ≥0,覆盖度随重采补齐。
    """
    with_comments = 0
    replied = 0
    for p in detail:
        try:
            comments = json.loads(p.comments_json or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        if not comments:
            continue
        with_comments += 1
        if any(isinstance(c, dict) and c.get("is_author") for c in comments):
            replied += 1
    ratio = round(replied / with_comments, 3) if with_comments else None
    return {"replied": replied, "with_comments": with_comments, "ratio": ratio}
