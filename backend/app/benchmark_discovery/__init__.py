"""对标博主搜寻:智能推荐 / 单博主评分的评估内核。

- context.py  由意图(+我的账号)建评估上下文
- querygen.py 意图 → 搜索词扩展
- engine.py   evaluate(候选) → 四项指标 + 综合分 + 依据(火爆度纯规则,其余 LLM)
"""

from app.benchmark_discovery.context import BenchmarkContext, build_context
from app.benchmark_discovery.engine import evaluate_candidate, popularity_score
from app.benchmark_discovery.querygen import expand_search_terms

__all__ = [
    "BenchmarkContext",
    "build_context",
    "evaluate_candidate",
    "popularity_score",
    "expand_search_terms",
]
