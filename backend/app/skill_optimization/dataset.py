"""时间留出数据划分:把博主已采笔记切成 train/val/test,供 SkillOpt env 使用。

防泄漏:按 published_at 时间排序,最旧→train(反思素材)、中间→val(门控)、最新→test(报告)。
口径统一:只保留主模态的笔记(少数派模态丢弃并计数),避免图文/视频混在一起打分失真。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.skill_optimization.rollout import Modality, extract_topic, gold_text, modality_of


@dataclass
class Sample:
    """一条训练样本:选题(rollout 输入)+ gold(风格参照)。"""

    id: int
    topic: str
    gold: str
    modality: Modality


@dataclass
class SplitResult:
    main_modality: Modality
    train: list[Sample] = field(default_factory=list)
    val: list[Sample] = field(default_factory=list)
    test: list[Sample] = field(default_factory=list)
    dropped_minority: int = 0
    total_kept: int = 0


def main_modality(posts: list) -> Modality:
    counts = Counter(modality_of(getattr(p, "content_subtype", "")) for p in posts)
    return "talking_video" if counts.get("talking_video", 0) > counts.get("image_text", 0) else "image_text"


def _sort_key(post):
    published = getattr(post, "published_at", None)
    ts = published.timestamp() if published is not None else 0.0
    return (ts, getattr(post, "id", 0))


def split_notes(
    posts: list,
    *,
    min_total: int = 12,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
) -> SplitResult:
    """按时间切 train/val/test。posts 应为某博主 active 笔记(调用方过滤)。"""
    modality = main_modality(posts)
    kept = [p for p in posts if modality_of(getattr(p, "content_subtype", "")) == modality]
    # gold 必须非空(视频去时间戳后可能空),否则没法打分。
    kept = [p for p in kept if gold_text(p, modality).strip()]
    dropped = len(posts) - len(kept)

    if len(kept) < min_total:
        raise ValueError(f"可用样本 {len(kept)} 篇(主模态 {modality}),少于最低 {min_total} 篇,请先采集更多笔记")

    kept.sort(key=_sort_key)  # 旧 → 新
    n = len(kept)
    n_val = max(1, round(n * val_ratio))
    n_test = max(1, round(n * test_ratio))
    if n_val + n_test >= n:
        n_val, n_test = 1, 1
    n_train = n - n_val - n_test

    def make(items: list) -> list[Sample]:
        return [Sample(id=getattr(p, "id", 0), topic=extract_topic(p), gold=gold_text(p, modality), modality=modality) for p in items]

    return SplitResult(
        main_modality=modality,
        train=make(kept[:n_train]),
        val=make(kept[n_train : n_train + n_val]),
        test=make(kept[n_train + n_val :]),
        dropped_minority=dropped,
        total_kept=n,
    )


def load_active_posts(db, tenant_id: int, blogger_id: int) -> list:
    """从 DB 取某博主 active 笔记(瘦封装,供 runner/env 调用)。"""
    from sqlalchemy import select

    from app.models import BloggerPost

    stmt = (
        select(BloggerPost)
        .where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger_id,
            BloggerPost.status == "active",
        )
        .order_by(BloggerPost.id.asc())
    )
    return list(db.scalars(stmt))
