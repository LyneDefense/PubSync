"""按用户需求给博主笔记打相关度分 —— 智能选材建快照的内核。

可靠性优先(教训见文末):
- **只打分、不写理由**:输出极小(每条 ~"{{i:0,v:88}}")→ 每次调用快、少超时。相关度分本身就是"为什么选它"的信号。
- **分批 + 有限并行**:每批 ~30 篇,最多 3 路并行(降低服务商并发争用导致的挂起)。
- **失败批重试一次**:某批超时/失败 → 收集后再跑一轮;单次抖动不再丢整批笔记。
- **有界降级**:仍失败的批默认 0 分;只有全批都失败才退化为空(退手动,绝不阻断)。

返回每条笔记的分,前端据此预勾选(高分)+ 一键放宽/自动补(取次高分),都无需再调模型。

历史教训:早先"一次给全部笔记打分**+逐条写理由**"→ 笔记多时输出爆炸、模型 read timeout → 兜底返回空 →
一篇选不出,还被"默认0分 + HTTP 200 + 日志写 timed out(我搜的是 timeout)"层层掩盖。去掉理由 + 分批 + 重试正是针对此。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)

_BATCH_SIZE = 30       # 每批笔记数
_MAX_WORKERS = 3       # 并行批数上限(过高会让服务商并发挂起)
_BATCH_TIMEOUT = 40    # 每批读超时(秒):快失败快重试,不再一批干等 90s

_PROMPT = """你在帮一个博主从对标账号的笔记里,挑出**贴合他需求**的笔记。

需求:{need}

下面是一批笔记(序号、标题、内容形态)。**逐条**给一个 0-100 的相关度分:越贴合需求越高;无关给 0-20;
需求偏某种形态(如口播/图文)时,形态不符的适当降分。

笔记:
{notes}

只输出紧凑 JSON(不要理由、不要多余字段):{{"s":[{{"i":序号,"v":分数}}]}}"""


def _score_batch(need: str, batch: list[dict[str, Any]], settings: Settings, timeout: int) -> dict[int, int]:
    """给一批笔记打分,返回 {批内序号: 分数}。失败 → 空(交由上层重试 / 降级)。"""
    listed = "\n".join(
        f"{i}. {(n.get('title') or '(无标题)')}｜形态:{n.get('subtype') or '未知'}" for i, n in enumerate(batch)
    )
    try:
        data = create_json_response(settings, _PROMPT.format(need=need, notes=listed), timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - 单批失败交上层重试,不阻断
        logger.warning("智能选材单批失败(待重试):%s", exc)
        return {}
    out: dict[int, int] = {}
    for item in (data.get("s") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(batch):
            out[idx] = max(0, min(100, int(item.get("v") or 0)))
    return out


def rank_notes_by_need(
    need: str,
    notes: list[dict[str, Any]],
    settings: Settings,
    *,
    timeout: int | None = None,
) -> dict[str, Any]:
    """notes: [{"id", "title", "subtype"}]。返回 {"name": str, "items": [{"post_id", "score", "reason"}]}。

    items 覆盖所有笔记(仍失败的补 0 分),按分降序。空需求/无笔记/全批失败 → {"name":"", "items":[]}。
    """
    need = (need or "").strip()
    if not need or not notes:
        return {"name": "", "items": []}

    per_batch_timeout = min(timeout or _BATCH_TIMEOUT, _BATCH_TIMEOUT)
    batch_of = {start: notes[start:start + _BATCH_SIZE] for start in range(0, len(notes), _BATCH_SIZE)}
    scores: dict[int, int] = {}  # 全局序号 → 分数

    def run_round(starts: list[int]) -> list[int]:
        failed: list[int] = []
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(starts))) as pool:
            futures = {pool.submit(_score_batch, need, batch_of[s], settings, per_batch_timeout): s for s in starts}
            for fut in as_completed(futures):
                start = futures[fut]
                res = fut.result()
                if res:
                    for local_idx, score in res.items():
                        scores[start + local_idx] = score
                else:
                    failed.append(start)
        return failed

    failed = run_round(list(batch_of))
    if failed:
        run_round(failed)  # 抖动/超时的批重试一次

    if not scores:  # 全批都失败 → 退化手动,不假装挑过
        return {"name": "", "items": []}
    items = [{"post_id": n["id"], "score": scores.get(i, 0), "reason": ""} for i, n in enumerate(notes)]
    items.sort(key=lambda it: it["score"], reverse=True)
    return {"name": _name_from_need(need), "items": items}


def _name_from_need(need: str) -> str:
    """用需求本身当默认快照名(可靠、零额外调用;用户可改)。"""
    n = need.strip()
    return f"{n[:14]}…" if len(n) > 14 else n
