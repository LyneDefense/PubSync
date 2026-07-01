"""T2 语义裁决:密度判不了的「模糊带」视频(半口播 / 剧情 / 卡点 / vlog),用大模型看
标题 + 转写片段 + 时长,判「口播」还是「非口播」。

只对 confidence=ambiguous 的少数视频调用,成本有界。分批 + 有限并行 + 失败降级:
判不出的批直接丢弃(调用方保留 T1 的临时猜测,绝不阻断采集)。返回 {post_id: subtype}。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.blogger_distillation.modality import TALKING_VIDEO, VISUAL_VIDEO
from app.config import Settings
from app.services.ai_service import create_json_response, is_ai_enabled

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20
_MAX_WORKERS = 3
_BATCH_TIMEOUT = 40
_EXCERPT = 300  # 转写片段截断字数

_PROMPT = """你在判定一批小红书/抖音视频的**内容形态**,只分两类:

- 口播:以「人对着镜头讲述 / 教学 / 口播解说」为主,**说的话本身就是内容主体**(露不露脸都算)。
- 非口播:以画面/表演为主——剧情、卡点混剪、vlog、风景展示、美食过程等,**台词只是点缀或几乎没有**。

下面每条给了标题、转写片段(可能不完整)、时长、字/秒密度。逐条判定。

笔记:
{notes}

只输出紧凑 JSON(不要理由):{{"r":[{{"i":序号,"t":"口播"或"非口播"}}]}}"""


def _label_to_subtype(label: str) -> str | None:
    text = str(label or "").strip()
    if "口播" == text or text in ("讲述", "教学", "talking"):
        return TALKING_VIDEO
    if "非口播" == text or text in ("剧情", "卡点", "vlog", "展示", "混剪", "visual"):
        return VISUAL_VIDEO
    if "口播" in text and "非口播" not in text:
        return TALKING_VIDEO
    if "非口播" in text:
        return VISUAL_VIDEO
    return None


def _adjudicate_batch(batch: list[dict[str, Any]], settings: Settings, timeout: int) -> dict[Any, str]:
    listed = "\n".join(
        f"{i}. 标题:{(n.get('title') or '(无标题)')[:60]}｜时长:{int(n.get('duration') or 0)}秒"
        f"｜密度:{n.get('cps', 0):.1f}字/秒｜转写:{(n.get('transcript') or '')[:_EXCERPT]}"
        for i, n in enumerate(batch)
    )
    try:
        data = create_json_response(settings, _PROMPT.format(notes=listed), timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - 单批失败交上层,保留临时猜测
        logger.warning("模态语义裁决单批失败(保留密度猜测):%s", exc)
        return {}
    out: dict[Any, str] = {}
    for item in (data.get("r") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        subtype = _label_to_subtype(item.get("t"))
        if subtype and 0 <= idx < len(batch):
            out[batch[idx]["id"]] = subtype
    return out


def adjudicate_modality(items: list[dict[str, Any]], settings: Settings, *, timeout: int | None = None) -> dict[Any, str]:
    """items: [{"id","title","transcript","duration"}](只传 ambiguous 的)。返回 {id: subtype}。

    未判出的 id 不在返回里 → 调用方保留 T1 密度猜测。无 key / 无 items → 空 dict。
    """
    usable = [it for it in (items or []) if it.get("id") is not None]
    if not usable or not is_ai_enabled(settings):
        return {}
    for it in usable:
        dur = it.get("duration") or 0
        it["cps"] = (len(str(it.get("transcript") or "")) / dur) if dur else 0.0
    per_batch_timeout = min(timeout or _BATCH_TIMEOUT, _BATCH_TIMEOUT)
    batches = [usable[i:i + _BATCH_SIZE] for i in range(0, len(usable), _BATCH_SIZE)]
    verdicts: dict[Any, str] = {}
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(batches))) as pool:
        futures = [pool.submit(_adjudicate_batch, b, settings, per_batch_timeout) for b in batches]
        for fut in as_completed(futures):
            verdicts.update(fut.result())
    return verdicts
