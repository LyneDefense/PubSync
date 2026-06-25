"""泛搜索的三路召回 + 交错去重 + 截断。

三路（都确定性"全跑",不靠 LLM 选）：
- A 搜索用户：方向词 → search_users。
- B 搜索笔记取作者：方向词 → search_notes → 去重取作者（捞"名字搜不到、靠内容出圈"的人名号）。
- C 种子关注列表：种子的 following 经筛子后的同类号（Phase 2;这里接收已解析好的列表）。

交错去重：通道之间、通道内各方向之间都 round-robin，避免某一路/某个方向把名额吃光（早期"娜姐被截断"的坑）。
通道调用以函数注入,便于单测用假数据。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.blogger_distillation.search import BloggerSearchResult


@dataclass
class WeightedDomain:
    label: str
    weight: float = 50.0  # 0-100


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
) -> list[BloggerSearchResult]:
    """三路召回 → 合并去重截断。单个方向/通道失败应由调用方吞掉(返回空列表)。"""
    labels = [d.label for d in domains if d.label.strip()]
    chan_users = _domain_interleave([_safe(search_users_fn, lbl) for lbl in labels])
    chan_authors = _domain_interleave([_safe(search_notes_authors_fn, lbl) for lbl in labels])
    chan_following = list(seed_following or [])
    return merge_interleave_dedupe([chan_users, chan_authors, chan_following], exclude_ids, cap)


def _safe(fn: Callable[[str], list[BloggerSearchResult]], arg: str) -> list[BloggerSearchResult]:
    """单路取数失败不阻断整体召回。"""
    try:
        return list(fn(arg) or [])
    except Exception:  # noqa: BLE001 - 某个方向/通道挂了就跳过它
        return []
