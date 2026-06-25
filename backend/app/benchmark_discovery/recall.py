"""泛搜索的三路召回 + 交错去重 + 截断。

三路（都确定性"全跑",不靠 LLM 选）：
- A 搜索用户：方向词 → search_users。
- B 搜索笔记取作者：方向词 → search_notes → 去重取作者（捞"名字搜不到、靠内容出圈"的人名号）。
- C 种子关注列表：种子的 following 经筛子后的同类号（Phase 2;这里接收已解析好的列表）。

交错去重：通道之间、通道内各方向之间都 round-robin，避免某一路/某个方向把名额吃光（早期"娜姐被截断"的坑）。
通道调用以函数注入,便于单测用假数据。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from app.blogger_distillation.search import BloggerSearchResult

logger = logging.getLogger(__name__)


@dataclass
class WeightedDomain:
    label: str
    weight: float = 50.0  # 0-100


@dataclass
class RecalledCandidate:
    """召回结果 + 溯源:命中了哪些方向(label,weight)、走了哪几条路、是否来自种子关注。

    溯源用来:① 给前端写"为什么是它"的理由;② 把命中方向的权重喂给打分(让权重真生效)。
    """

    result: BloggerSearchResult
    matched: list[tuple[str, float]] = field(default_factory=list)  # 命中方向(按权重降序)
    channels: list[str] = field(default_factory=list)              # {"users","authors","following"}
    from_seed: bool = False                                        # 来自某个种子的关注列表


def _key(r: BloggerSearchResult) -> str:
    return (r.external_id or r.homepage_url or "").strip()


def _domain_interleave(per_domain: list[list[BloggerSearchResult]]) -> list[BloggerSearchResult]:
    """一个通道内、跨方向 round-robin 拉平,让各方向轮流出号。"""
    out: list[BloggerSearchResult] = []
    idx = 0
    while any(idx < len(lst) for lst in per_domain):
        for lst in per_domain:
            if idx < len(lst):
                out.append(lst[idx])
        idx += 1
    return out


def merge_interleave_dedupe(
    channels: list[list[BloggerSearchResult]],
    exclude_ids: Iterable[str],
    cap: int,
) -> list[BloggerSearchResult]:
    """通道之间 round-robin 取,去重 + 排除已看过,截到 cap。"""
    seen = {str(x).strip() for x in exclude_ids if str(x).strip()}
    out: list[BloggerSearchResult] = []
    idx = 0
    lengths = [len(c) for c in channels]
    while len(out) < cap and any(idx < n for n in lengths):
        for c in channels:
            if idx < len(c):
                r = c[idx]
                k = _key(r)
                if k and k not in seen:
                    seen.add(k)
                    out.append(r)
                    if len(out) >= cap:
                        break
        idx += 1
    return out


def recall(
    domains: list[WeightedDomain],
    *,
    search_users_fn: Callable[[str], list[BloggerSearchResult]],
    search_notes_authors_fn: Callable[[str], list[BloggerSearchResult]],
    seed_following: list[BloggerSearchResult] | None = None,
    cap: int,
    exclude_ids: Iterable[str] = (),
    on_domain: Callable[[str, int, int], None] | None = None,
) -> list[RecalledCandidate]:
    """三路召回 → 合并去重截断,带溯源。单个方向/通道失败由 _safe 吞掉(返回空列表)。

    on_domain(label, 用户数, 作者数):每搜完一个方向回调一次,供任务层写进度事件。
    """
    labels = [(d.label.strip(), d.weight) for d in domains if d.label.strip()]
    prov: dict[str, dict] = {}

    def _tag(r: BloggerSearchResult, label: str, weight: float, channel: str, from_seed: bool = False) -> None:
        k = _key(r)
        if not k:
            return
        p = prov.setdefault(k, {"matched": {}, "channels": set(), "from_seed": False})
        if label:
            p["matched"][label] = max(p["matched"].get(label, 0.0), weight)
        p["channels"].add(channel)
        if from_seed:
            p["from_seed"] = True

    users_per_domain: list[list[BloggerSearchResult]] = []
    authors_per_domain: list[list[BloggerSearchResult]] = []
    for label, weight in labels:
        users = _safe(search_users_fn, label, channel="搜用户", domain=label)
        authors = _safe(search_notes_authors_fn, label, channel="搜笔记取作者", domain=label)
        for r in users:
            _tag(r, label, weight, "users")
        for r in authors:
            _tag(r, label, weight, "authors")
        users_per_domain.append(users)
        authors_per_domain.append(authors)
        # 每方向命中数:判断「B 路到底有没有出号」最直接的证据,也回调给进度条。
        logger.info("泛搜索·召回 方向=「%s」 搜用户=%d 搜笔记取作者=%d", label, len(users), len(authors))
        if on_domain is not None:
            try:
                on_domain(label, len(users), len(authors))
            except Exception:  # noqa: BLE001 - 进度回调失败不能影响召回
                pass

    chan_users = _domain_interleave(users_per_domain)
    chan_authors = _domain_interleave(authors_per_domain)
    chan_following = list(seed_following or [])
    for r in chan_following:
        _tag(r, "", 0.0, "following", from_seed=True)

    exclude_n = len({str(x).strip() for x in exclude_ids if str(x).strip()})
    merged = merge_interleave_dedupe([chan_users, chan_authors, chan_following], exclude_ids, cap)
    out: list[RecalledCandidate] = []
    for r in merged:
        p = prov.get(_key(r), {"matched": {}, "channels": set(), "from_seed": False})
        out.append(RecalledCandidate(
            result=r,
            matched=sorted(p["matched"].items(), key=lambda kv: -kv[1]),
            channels=sorted(p["channels"]),
            from_seed=bool(p["from_seed"]),
        ))
    logger.info(
        "泛搜索·召回汇总 通道[用户=%d 笔记作者=%d 种子关注=%d] 排除已看过=%d → 去重截断后=%d (cap=%d)",
        len(chan_users), len(chan_authors), len(chan_following), exclude_n, len(merged), cap,
    )
    return out


def _safe(
    fn: Callable[[str], list[BloggerSearchResult]], arg: str, *, channel: str = "", domain: str = ""
) -> list[BloggerSearchResult]:
    """单路取数失败不阻断整体召回(但要记一条警告,免得静默退化看不出来)。"""
    try:
        return list(fn(arg) or [])
    except Exception as exc:  # noqa: BLE001 - 某个方向/通道挂了就跳过它
        logger.warning("泛搜索·召回 单路失败已跳过 通道=%s 方向=「%s」: %s", channel, domain, exc)
        return []
