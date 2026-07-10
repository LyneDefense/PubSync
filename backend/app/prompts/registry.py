"""Prompt 站点注册表:登记「函数身份」(name/version/model/owner),**不存正文**。

见 docs/prompt治理_方案设计.md 支柱三(P1)。因为我们的 prompt 是动态组装的函数(内容随 ctx 变),
注册表登记的是「哪个函数 + 哪一版」这张身份证,不是它每次生成的正文。

- 装饰器 @prompt 贴在生成 prompt 的函数上,**零成本自注册、调用方式不变**(原样返回函数);
- list_prompts() 给全站一览,取代手维护的 docs/prompt改造清单.md;
- get(name).version 供 run 时记进 report_json,产物可追溯是哪版 prompt 产的。

注:靠 import 副作用注册——list_prompts() 只反映已 import 的模块;要全量一览,先 load_all_sites()。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PromptSite:
    name: str
    version: str
    func: Callable
    model: str | None = None
    kind: str = "agent_system"  # agent_system | one_shot | vlm_system | critic
    owner: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


PROMPT_REGISTRY: dict[str, PromptSite] = {}


def prompt(
    name: str,
    *,
    version: str,
    model: str | None = None,
    kind: str = "agent_system",
    owner: str = "",
    **meta: Any,
) -> Callable:
    """装饰器:把被装饰函数登记为一个 prompt 站点。返回原函数,调用方式一个字不改。"""

    def deco(func: Callable) -> Callable:
        PROMPT_REGISTRY[name] = PromptSite(
            name=name, version=version, func=func, model=model, kind=kind, owner=owner, meta=dict(meta)
        )
        return func

    return deco


def get(name: str) -> PromptSite:
    return PROMPT_REGISTRY[name]


def list_prompts() -> list[PromptSite]:
    """全站已登记的 prompt 站点(按 name 排序)。"""
    return sorted(PROMPT_REGISTRY.values(), key=lambda p: p.name)


def load_all_sites() -> None:
    """import 各域贴了 @prompt 的模块,保证 list_prompts() 全量。放函数里而非顶层,避免循环 import。"""
    from app.blogger_distillation.service import distill_engine  # noqa: F401
    from app.xhs_creation.agent import guide  # noqa: F401
