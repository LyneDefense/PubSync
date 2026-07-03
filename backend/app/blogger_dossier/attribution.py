"""爆文归因(档案③,LLM,按钮触发):爆发组 vs 常态组对比 → 「有据的假设」,不承诺因果。

方法论:归因靠对比(爆 vs 不爆、转折前 vs 后),曲线本身只回答"何时爆"。
三个坑显式规避:相关≠因果、幸存者偏差(必带常态组对照)、外部变量(推流/热点)不可观测要承认。
"""

from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.models import BloggerPost
from app.models.common import utc_now
from app.services.ai_service import create_json_response

_MAX_BURSTS = 6      # 送 LLM 的爆文数上限
_MAX_NORMALS = 10    # 常态组对照(只给标题)上限
_TIMEOUT = 90


def run_attribution(settings: Settings, posts: list[BloggerPost], trajectory: dict[str, Any]) -> dict[str, Any]:
    """基于轨迹的爆发点做归因。无爆发点 → ValueError(诚实拒绝,前端显示"增长平稳")。"""
    bursts = trajectory.get("bursts") or []
    if not bursts:
        raise ValueError("未检测到显著爆发点：该账号增长平稳，暂无可归因的爆文")
    by_id = {p.id: p for p in posts}
    burst_posts = [by_id[b["post_id"]] for b in bursts if b.get("post_id") in by_id][:_MAX_BURSTS]
    burst_ids = {p.id for p in burst_posts}
    normals = sorted(
        (p for p in posts if p.id not in burst_ids and p.published_at),
        key=lambda p: abs((p.like_count or 0) - _median_like(posts)),
    )[:_MAX_NORMALS]

    prompt = f"""你在分析一个博主「为什么能爆」。下面是 TA 的爆文组与常态组,请**只基于给出的事实**提炼可复制的爆发假设。

硬边界：
- 输出合法 JSON,不要 Markdown/解释;假设 ≤4 条,每条必须引用具体证据(标题/形态/数据);
- 这是「有据的假设」不是因果结论——平台推流/蹭热点等外部因素观察不到,须在 summary 里承认;
- 单篇爆款可能纯运气,优先提炼**多篇爆文的共性**;没把握的不要编。

轨迹概览：{trajectory.get("summary", "")}

爆文组（逐篇）：
{_render_bursts(burst_posts)}

常态组（对照,仅标题·赞）：
{_render_normals(normals)}

只输出：{{"hypotheses": [{{"claim": "假设一句话", "evidence": "引用的具体证据", "confidence": "高/中/低"}}], "summary": "一段话总结,含外部因素不可观测的承认"}}"""
    data = create_json_response(settings, prompt, timeout=_TIMEOUT)
    hypotheses = [
        {"claim": str(h.get("claim") or "").strip(), "evidence": str(h.get("evidence") or "").strip(),
         "confidence": str(h.get("confidence") or "中").strip()}
        for h in (data.get("hypotheses") if isinstance(data, dict) else None) or []
        if isinstance(h, dict) and str(h.get("claim") or "").strip()
    ]
    return {
        "generated_at": utc_now().isoformat(),
        "burst_count": len(burst_posts),
        "hypotheses": hypotheses[:4],
        "summary": str((data or {}).get("summary") or "").strip(),
    }


def _median_like(posts: list[BloggerPost]) -> int:
    likes = sorted(p.like_count or 0 for p in posts)
    return likes[len(likes) // 2] if likes else 0


def _render_bursts(posts: list[BloggerPost]) -> str:
    lines = []
    for p in posts:
        date = p.published_at.date().isoformat() if p.published_at else "?"
        lines.append(f"· {date}｜{p.title}｜{'视频' if p.content_type == 'video' else '图文'}｜赞{p.like_count}藏{p.favorite_count}评{p.comment_count}")
        excerpt = (p.transcript_text or p.body_text or "").strip()[:150]
        if excerpt:
            lines.append(f"  内容摘要：{excerpt}")
        image_text = (p.image_text or "").strip()[:120]
        if image_text:
            lines.append(f"  图内要点：{image_text}")
    return "\n".join(lines)


def _render_normals(posts: list[BloggerPost]) -> str:
    return "\n".join(f"· {p.title}｜赞{p.like_count}" for p in posts) or "（无）"


def parse_attribution(raw_json: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_json or "")
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) and data.get("hypotheses") is not None else None
