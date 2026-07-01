"""按用户需求给博主笔记打相关度分 —— 智能选材建快照的内核(一次便宜的标题级模型调用)。

返回**每条**笔记的分数,前端据此:预勾选(高分)+ 一键「放宽/自动补」(降门槛 / 取次高分),都无需再调模型。
失败 / 空需求 / 无素材 → 返回空,前端退化为手动挑,绝不阻断。与 appraisal.judge_note_relevance 同源思路。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

_PROMPT = """你在帮一个博主从「另一个对标账号」的笔记里,挑出**贴合他需求**的笔记,整理成一份选材。

他的需求:{need}

下面是对标账号的笔记(带序号、标题、内容形态)。逐条给一个 **0-100 的相关度分**:
- 越贴合他的需求分越高;完全无关给 0-20;拿不准给中间分。
- 尽量利用「内容形态」:如果需求偏某种形态(如口播/图文),形态不符的适当降分。
再给这份选材起一个**简短的中文快照名**(≤12 字,概括这批笔记的主题)。

笔记列表:
{notes}

只输出 JSON:{{"name":"快照名","items":[{{"i":序号,"score":0-100,"reason":"一句话为什么"}}]}}"""


def rank_notes_by_need(
    need: str,
    notes: list[dict[str, Any]],
    settings: Settings,
    *,
    timeout: int | None = None,
) -> dict[str, Any]:
    """notes: [{"id", "title", "subtype"}]。返回 {"name": str, "items": [{"post_id", "score", "reason"}]}。

    items 覆盖所有传入笔记(未被模型评分的补 0 分),按分数降序;失败/空需求 → {"name":"", "items":[]}。
    """
    need = (need or "").strip()
    if not need or not notes:
        return {"name": "", "items": []}
    listed = "\n".join(
        f"{i}. {(n.get('title') or '(无标题)')}｜形态:{n.get('subtype') or '未知'}" for i, n in enumerate(notes)
    )[:6000]
    try:
        data = create_json_response(settings, _PROMPT.format(need=need, notes=listed), timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - 选材助手失败不该挡手动建快照
        logger.warning("智能选材失败,退化为手动:%s", exc)
        return {"name": "", "items": []}
    if not isinstance(data, dict):
        return {"name": "", "items": []}

    scored: dict[int, dict[str, Any]] = {}
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(notes):
            score = max(0, min(100, int(item.get("score") or 0)))
            scored[idx] = {"post_id": notes[idx]["id"], "score": score, "reason": str(item.get("reason") or "").strip()}
    # 覆盖所有笔记(模型漏评的补 0 分),按分数降序 → 前端预勾选 / 放宽 / 自动补都用这一份。
    items = [scored.get(i, {"post_id": n["id"], "score": 0, "reason": ""}) for i, n in enumerate(notes)]
    items.sort(key=lambda it: it["score"], reverse=True)
    return {"name": str(data.get("name") or "").strip()[:20], "items": items}
