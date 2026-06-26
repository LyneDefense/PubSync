"""意图 → 搜索词扩展(供推荐/评分的候选拉取用)。

注:泛搜索的「细分领域/方向」推荐(suggest_subniches / expand_directions)已随泛搜索一起移除,
本文件只保留 expand_search_terms。
"""

from __future__ import annotations

import logging

from app.benchmark_discovery.context import BenchmarkContext
from app.config import Settings
from app.services.ai_service import create_json_response

logger = logging.getLogger(__name__)


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
