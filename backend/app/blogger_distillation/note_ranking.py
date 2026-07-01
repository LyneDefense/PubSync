"""按用户需求给博主笔记打相关度分 —— 智能选材建快照的内核。

**分批 + 并行**:每批 ~30 篇一次模型调用,输出小、快、不超时;各批并行,墙钟≈最慢一批。
某批失败只让那批默认 0 分(有界),不再"一超时全军覆没"。返回每条笔记的分,前端据此
预勾选(高分)+ 一键放宽/自动补(取次高分),都无需再调模型。失败/空需求 → 空,退化手动,绝不阻断。

历史教训:早先"一次给全部笔记打分+写理由"在博主笔记多时输出爆炸 → read timeout → 兜底返回空 →
一篇选不出,还被"默认0分 + HTTP 200"掩盖。分批正是针对这个根因。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

_BATCH_SIZE = 30      # 每批笔记数:小到模型能稳定逐条评分、输出不超时
_MAX_WORKERS = 5      # 并行批数上限

_PROMPT = """你在帮一个博主从对标账号的笔记里,挑出**贴合他需求**的笔记。

他的需求:{need}

下面是一批笔记(带序号、标题、内容形态)。逐条给一个 **0-100 的相关度分**(越贴合越高;无关给 0-20),
再给**一句≤15字**的理由。尽量利用「形态」:需求偏某形态时,形态不符的适当降分。

笔记:
{notes}

只输出 JSON:{{"items":[{{"i":序号,"score":0-100,"reason":"一句话"}}]}}"""


def _score_batch(need: str, batch: list[dict[str, Any]], settings: Settings, timeout: int | None) -> dict[int, dict[str, Any]]:
    """给一批笔记打分,返回 {批内序号: {score, reason}}。失败 → 空(该批默认 0 分,有界降级)。"""
    listed = "\n".join(
        f"{i}. {(n.get('title') or '(无标题)')}｜形态:{n.get('subtype') or '未知'}" for i, n in enumerate(batch)
    )
    try:
        data = create_json_response(settings, _PROMPT.format(need=need, notes=listed), timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - 单批失败只降级该批,不阻断整体
        logger.warning("智能选材单批失败(该批默认0分):%s", exc)
        return {}
    out: dict[int, dict[str, Any]] = {}
    for item in (data.get("items") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(batch):
            out[idx] = {"score": max(0, min(100, int(item.get("score") or 0))), "reason": str(item.get("reason") or "").strip()}
    return out


def rank_notes_by_need(
    need: str,
    notes: list[dict[str, Any]],
    settings: Settings,
    *,
    timeout: int | None = None,
) -> dict[str, Any]:
    """notes: [{"id", "title", "subtype"}]。返回 {"name": str, "items": [{"post_id", "score", "reason"}]}。

    items 覆盖所有笔记(某批失败/模型漏评的补 0 分),按分降序。空需求/无笔记 → {"name":"", "items":[]}。
    """
    need = (need or "").strip()
    if not need or not notes:
        return {"name": "", "items": []}

    batches = [(start, notes[start:start + _BATCH_SIZE]) for start in range(0, len(notes), _BATCH_SIZE)]
    merged: dict[int, dict[str, Any]] = {}  # 全局序号 → {score, reason}
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(batches))) as pool:
        futures = {pool.submit(_score_batch, need, batch, settings, timeout): start for start, batch in batches}
        for fut in as_completed(futures):
            start = futures[fut]
            for local_idx, sc in fut.result().items():
                merged[start + local_idx] = sc

    if not merged:  # 全批都失败(而非"都不相关")→ 退化为手动,不假装挑过
        return {"name": "", "items": []}
    items = [
        {"post_id": n["id"], "score": (merged.get(i) or {}).get("score", 0), "reason": (merged.get(i) or {}).get("reason", "")}
        for i, n in enumerate(notes)
    ]
    items.sort(key=lambda it: it["score"], reverse=True)
    return {"name": _name_from_need(need), "items": items}


def _name_from_need(need: str) -> str:
    """用需求本身当默认快照名(可靠、零额外调用;用户可改)。"""
    n = need.strip()
    return f"{n[:14]}…" if len(n) > 14 else n
