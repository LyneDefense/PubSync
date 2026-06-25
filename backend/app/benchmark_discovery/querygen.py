from __future__ import annotations

import concurrent.futures
import logging
import time
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


@dataclass
class SubNiche:
    """细分领域(角度收窄用):名 + 一句理由。"""

    label: str
    reason: str = ""


def _json_with_timeout(settings: Settings, prompt: str, timeout_s: int) -> dict:
    """给 LLM 调用套一个硬超时(底层 httpx 默认 180s,交互式角度推荐不能等那么久)。

    超时/失败抛异常,由调用方走规则兜底。底层请求线程可能还在跑,但用户立即拿到兜底。
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(create_json_response, settings, prompt).result(timeout=max(5, timeout_s))


def _rule_subniches(domains: list[str], shown: set[str], n: int) -> list[SubNiche]:
    """规则兜底:用领域 + 常见角度后缀拼细分,跳过已展示过的。"""
    suffixes = ["入门科普", "避坑指南", "真实测评", "案例拆解", "对比攻略", "进阶玩法", "答疑"]
    out: list[SubNiche] = []
    for d in domains:
        d = d.strip()
        if not d:
            continue
        for suf in suffixes:
            label = f"{d}{suf}"
            if label not in shown and label not in {s.label for s in out}:
                out.append(SubNiche(label=label, reason="按常见角度拆的"))
            if len(out) >= n:
                return out
    return out[:n]


def suggest_subniches(
    settings: Settings,
    domains: list[str],
    *,
    selected: list[str] | None = None,
    rejected: list[str] | None = None,
    shown: list[str] | None = None,
    n: int = 4,
) -> list[SubNiche]:
    """根据用户已选/已拒的细分领域,让 agent 再推一批「更贴近、且不重复」的细分领域。

    铁律:LLM 超时/失败/乱格式 → 规则兜底,流程不断。已展示过的(选中+拒绝+略过)不再出。
    """
    domains = [d.strip() for d in domains if d.strip()]
    selected = [s for s in (selected or []) if s.strip()]
    rejected = [r for r in (rejected or []) if r.strip()]
    shown_set = {s.strip() for s in (shown or []) if s.strip()} | set(selected) | set(rejected)
    if not domains:
        return []
    timeout_s = int(getattr(settings, "discovery_angle_timeout_seconds", 30) or 30)
    prompt = (
        "你在帮一个不知道该对标谁的博主缩小范围。大方向是:" + "、".join(domains) + "。\n"
        + (f"他已经选中的细分角度:{'、'.join(selected)}\n" if selected else "")
        + (f"他明确不想要的角度:{'、'.join(rejected)}\n" if rejected else "")
        + (f"已经给他看过、不要重复的:{'、'.join(sorted(shown_set))}\n" if shown_set else "")
        + f"请再给 {n} 个**新的、更具体、可在小红书/抖音搜索的**细分角度(中文 2-10 字),"
        "尽量贴近他已选角度的调性、避开他不想要的;每个配一句话理由。\n"
        '只输出 JSON:{"subniches":[{"label":"细分角度","reason":"一句话"}]}'
    )
    try:
        data = _json_with_timeout(settings, prompt, timeout_s)
        raw = data.get("subniches") if isinstance(data, dict) else None
        out: list[SubNiche] = []
        seen: set[str] = set(shown_set)
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            if not label or label in seen:
                continue
            seen.add(label)
            out.append(SubNiche(label=label, reason=str(item.get("reason", "")).strip()))
        out = out[:n]
        if out:
            logger.info("泛搜索·推角度 领域=%s 已选=%s → 新推%d个:%s",
                        domains, selected, len(out), [s.label for s in out])
            return out
        logger.info("泛搜索·推角度 LLM未给出新角度,走规则兜底 领域=%s", domains)
        return _rule_subniches(domains, shown_set, n)
    except Exception as exc:  # noqa: BLE001 - 超时/失败 → 规则兜底,绝不卡住
        logger.warning("泛搜索·推角度失败,规则兜底:%s(%s)", exc, type(exc).__name__)
        return _rule_subniches(domains, shown_set, n)


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
    # 注意:本调用同步发生在 POST /start 请求里,LLM 默认 180s 超时;慢/挂会让前端「准备中…」一直转。
    t0 = time.monotonic()
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
            logger.info("泛搜索·扩展方向 LLM未给出有效方向,退回原始领域%s (用时%.1fs)", clean, time.monotonic() - t0)
            return fallback
        out.sort(key=lambda d: d.weight, reverse=True)
        out = out[:max_directions]
        for i, d in enumerate(out):
            d.selected = i < 4  # 默认勾选 top 4
        logger.info(
            "泛搜索·扩展方向 输入%s → LLM给出%d个(用时%.1fs):%s",
            clean, len(out), time.monotonic() - t0, [(d.label, round(d.weight)) for d in out],
        )
        return out
    except Exception as exc:  # noqa: BLE001 - 扩展失败退回原始领域,绝不卡住
        logger.warning("泛搜索·扩展方向失败,退回原始领域(用时%.1fs):%s", time.monotonic() - t0, exc)
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
