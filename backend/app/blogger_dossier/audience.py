"""受众需求(档案③,LLM,按钮触发):从**读者评论**聚合「读者最常问」——选题输入,受众侧,正交于蒸馏。

方法:取已采顶层评论里的读者评论(is_author=false),按点赞热度取样,让 LLM 归纳**反复出现**的问题/关注点。
诚实边界:依据已采顶层评论(非全量、非穷举);不采楼中楼;小红书拿不到浏览量/推流,不碰。
"""

from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.models import BloggerPost
from app.models.common import utc_now
from app.services.ai_service import create_json_response

_MAX_COMMENTS = 120   # 送 LLM 的读者评论上限(按热度取,控 prompt 体量)
_MIN_COMMENTS = 8     # 少于此 → 诚实拒绝(样本不足,归纳不出共性)
_TIMEOUT = 90


def _reader_comments(posts: list[BloggerPost]) -> list[dict[str, Any]]:
    """全池读者评论(去博主回复),按点赞热度降序、截断。评论已在采集时按热度排序,这里再统一排一次。"""
    out: list[dict[str, Any]] = []
    for post in posts:
        try:
            arr = json.loads(post.comments_json or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(arr, list):
            continue
        for c in arr:
            if not isinstance(c, dict) or c.get("is_author"):
                continue
            text = str(c.get("content") or "").strip()
            if len(text) < 2:
                continue
            out.append({"text": text[:120], "like": int(c.get("like_count") or 0)})
    out.sort(key=lambda x: x["like"], reverse=True)
    return out[:_MAX_COMMENTS]


def run_audience(settings: Settings, posts: list[BloggerPost]) -> dict[str, Any]:
    """归纳读者最常问。读者评论过少 → ValueError(诚实拒绝,前端提示多采评论)。"""
    comments = _reader_comments(posts)
    if len(comments) < _MIN_COMMENTS:
        raise ValueError(f"读者评论仅 {len(comments)} 条，不足以归纳受众需求；可多采集些评论后再试")

    rendered = "\n".join(f"· [{c['like']}赞] {c['text']}" for c in comments)
    prompt = f"""你在分析一个博主的**读者评论**,帮创作者看清「读者最想知道什么」——用于选题。下面是按点赞热度排序的读者评论(不含博主自己的回复)。

硬边界:
- 只基于给出的评论,别脑补;输出合法 JSON,不要 Markdown;
- 优先**多条评论反复出现**的问题/关注点,别把单条孤立评论当共性;
- questions ≤6 条,每条 {{theme: 一句话概括读者在问什么, sample: 一条最能代表的原话}};
- focus_points ≤6 个短词(读者高频关注的点/情绪,如 价格/避坑/真实性/适合谁/售后);
- note: 一句话说明依据了多少条评论、非穷举。

读者评论(热度降序):
{rendered}

只输出:{{"questions": [{{"theme": "", "sample": ""}}], "focus_points": ["", ""], "note": ""}}"""
    data = create_json_response(settings, prompt, timeout=_TIMEOUT)
    return _normalize(data, len(comments))


def _normalize(data: Any, comment_count: int) -> dict[str, Any]:
    obj = data if isinstance(data, dict) else {}
    questions = [
        {"theme": str(q.get("theme") or "").strip(), "sample": str(q.get("sample") or "").strip()}
        for q in (obj.get("questions") or [])
        if isinstance(q, dict) and str(q.get("theme") or "").strip()
    ]
    focus = [str(f).strip() for f in (obj.get("focus_points") or []) if str(f).strip()]
    return {
        "generated_at": utc_now().isoformat(),
        "comment_count": comment_count,
        "questions": questions[:6],
        "focus_points": focus[:6],
        "note": str(obj.get("note") or "").strip(),
    }


def parse_audience(raw_json: str) -> dict[str, Any] | None:
    """读回存库结果(复用 blogger.attribution_json 列)。旧归因数据无 questions → 视为无。"""
    try:
        data = json.loads(raw_json or "")
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) and data.get("questions") is not None else None
