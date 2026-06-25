from __future__ import annotations

import logging
from dataclasses import dataclass

from app.benchmark_discovery.context import BenchmarkContext
from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)


@dataclass
class Direction:
    """泛搜索 S2 的一个扩展方向:名 + 默认权重(0-100) + 一句理由 + 是否默认选中。"""

    label: str
    weight: float = 50.0
    reason: str = ""
    selected: bool = True


def expand_directions(
    settings: Settings,
    domains: list[str],
    *,
    seed_fingerprint: str = "",
    max_directions: int = 10,
) -> list[Direction]:
    """把用户填的多个领域(+可选种子内容指纹)扩成「带默认权重的方向」,默认勾选 top 4。

    铁律:LLM 失败/超时/乱格式 → 直接退回"用户原始领域当方向"(权重 60),流程不断。
    """
    clean = [d.strip() for d in domains if d.strip()]
    fallback = [Direction(label=d, weight=60.0, reason="你填的方向", selected=True) for d in clean]
    if not clean:
        return []
    prompt = (
        "你是小红书/抖音对标博主搜寻助手。用户想做的内容方向(可能多个)如下,"
        "请扩展出若干更具体、可在平台搜索的子方向(中文,2-8字),每个给一个 0-100 的权重"
        "(越贴近用户目标越高)和一句理由。\n"
        f"用户方向:{', '.join(clean)}\n"
        + (f"参考(用户想对标的账号画像):{seed_fingerprint[:600]}\n" if seed_fingerprint.strip() else "")
        + f'只输出 JSON:{{"directions":[{{"label":"子方向","weight":0-100,"reason":"一句话"}}]}},'
        f"最多 {max_directions} 个,按权重降序。"
    )
    try:
        data = create_json_response(settings, prompt)
        raw = data.get("directions") if isinstance(data, dict) else None
        out: list[Direction] = []
        seen: set[str] = set()
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            if not label or label in seen:
                continue
            seen.add(label)
            try:
                weight = max(0.0, min(100.0, float(item.get("weight", 50))))
            except (TypeError, ValueError):
                weight = 50.0
            out.append(Direction(label=label, weight=round(weight, 1), reason=str(item.get("reason", "")).strip()))
        if not out:
            return fallback
        out.sort(key=lambda d: d.weight, reverse=True)
        out = out[:max_directions]
        for i, d in enumerate(out):
            d.selected = i < 4  # 默认勾选 top 4
        return out
    except Exception as exc:  # noqa: BLE001 - 扩展失败退回原始领域,绝不卡住
        logger.warning("方向扩展失败,退回原始领域:%s", exc)
        return fallback


def expand_search_terms(settings: Settings, ctx: BenchmarkContext, max_terms: int = 5) -> list[str]:
    """把用户意图扩展成若干搜索词,用于拉候选池。LLM 失败时退回 [niche]。"""
    niche = ctx.niche.strip()
    if not niche:
        return []
    prompt = (
        "你是小红书/抖音的对标博主搜寻助手。用户想做的内容方向如下,请给出用于在平台搜索框里"
        "找到该方向头部博主的若干「搜索关键词」(中文,2-6字,具体可搜,不要句子、不要标点)。\n"
        f"领域:{niche}\n"
        f"受众:{ctx.audience or '未填'}\n"
        f"目标:{ctx.goal or '未填'}\n"
        f'只输出 JSON:{{"terms": ["词1","词2", ...]}},最多 {max_terms} 个,按相关度排序。'
    )
    try:
        data = create_json_response(settings, prompt)
    except Exception as exc:  # noqa: BLE001 - 扩展失败不应阻断,退回 niche
        logger.warning("搜索词扩展失败,退回原始领域词:%s", exc)
        return [niche]
    raw = data.get("terms") if isinstance(data, dict) else None
    terms: list[str] = []
    for item in raw or []:
        if isinstance(item, str) and item.strip():
            term = item.strip()
            if term not in terms:
                terms.append(term)
    terms = terms[:max_terms]
    return terms or [niche]
