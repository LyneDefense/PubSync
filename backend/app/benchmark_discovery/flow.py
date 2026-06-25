"""泛搜索（找对标）三列工作台：候选 / 种子 / 已选,持续存在的一个会话,东西只往前流。

- 候选：召回来的号。每个号可「设为种子」或「选入对标」(移出候选,不再回候选)。
- 种子：用来「按种子找候选」(拉其关注列表)。可移除、可「选入对标」(复制,种子保留)。
- 已选：「保存到对标库」(幂等,可随时存、增量存)。

确定性控制器,只在「扩展方向」节点借 LLM(失败走规则兜底);召回(打 TikHub)由调用方放进异步任务。
等待用户发生在 HTTP 边界。空闲超过 expires_at 由清理任务标 expired。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmark_discovery.querygen import expand_directions
from app.benchmark_discovery.ranking import CandidateSignals, composite_score
from app.benchmark_discovery.recall import RecalledCandidate, WeightedDomain, recall
from app.blogger_distillation.search import (
    BloggerSearchResult,
    get_user_following,
    search_bloggers,
    search_note_authors,
)
from app.config import Settings
from app.models import BloggerProfile
from app.models.benchmark_discovery import BenchmarkDiscoverySession

logger = logging.getLogger(__name__)

# 机构号关键词兜底(平台认证标识取不到时用)。
INSTITUTION_HINTS = ("官方", "旗舰", "品牌", "有限公司", "集团", "机构", "客服", "商城", "专卖", "store", "official")
# 平台认证文案里出现这些 → 判机构(企业认证)。
ENTERPRISE_VERIFY_HINTS = ("企业", "公司", "品牌", "官方", "商家", "enterprise", "company", "brand")
# 来自种子关注、又没命中具体方向时给的基础匹配权重(让"找相似"出来的号有个像样的分,不被火爆度淹没)。
SEED_MATCH_WEIGHT = 65.0
DEST_SEED = "seed"
DEST_SELECTED = "selected"


def is_institution_account(platform: str, name: str, desc: str, raw: dict | None) -> bool:
    """是不是机构/企业号。优先用平台认证标识(最准),取不到再退回关键词。

    说明:TikHub 各端点的认证字段语义不完全统一,这里做 best-effort——
    命中明确的企业认证标识就判机构,否则看名字/简介里的机构词。
    """
    raw = raw or {}
    if platform == "xhs":
        vt = raw.get("red_official_verify_type")
        if isinstance(vt, (int, float)) and int(vt) >= 2:  # 2+ 常为企业认证(个人红V一般为 1)
            return True
    else:  # douyin
        reason = str(raw.get("enterprise_verify_reason") or raw.get("custom_verify") or "")
        if reason.strip() and any(h in reason for h in ENTERPRISE_VERIFY_HINTS):
            return True
    verify_text = " ".join(
        str(raw.get(k, "")) for k in ("verify_reason", "red_official_verify_content", "official_verify", "verify_info")
    )
    if any(h in verify_text for h in ENTERPRISE_VERIFY_HINTS):
        return True
    blob = f"{name} {desc}".lower()
    return any(h.lower() in blob for h in INSTITUTION_HINTS)


def _signals(rc: RecalledCandidate, platform: str) -> CandidateSignals:
    """从召回结果 + 溯源拿客观信号喂给打分。命中方向权重在这里真正赋值(修掉"权重不起作用")。"""
    r = rc.result
    matched_weight = min(100.0, sum(w for _, w in rc.matched))
    if rc.from_seed and matched_weight <= 0:
        matched_weight = SEED_MATCH_WEIGHT
    return CandidateSignals(
        external_id=r.external_id,
        follower_count=r.follower_count or 0,
        like_samples=[],
        is_personal=not is_institution_account(platform, r.display_name, r.description, r.raw),
        matched_weight=matched_weight,
        popularity_known=bool(getattr(r, "follower_known", True)),
    )


def _reason_line(rc: RecalledCandidate) -> str:
    """为什么推荐它:命中方向 + 走哪条路发现的。数据(粉丝/号型)前端单独展示,这里不重复。"""
    parts: list[str] = []
    if rc.matched:
        parts.append("命中方向" + "".join(f"「{lbl}」" for lbl, _ in rc.matched[:3]))
    if rc.from_seed or "following" in rc.channels:
        parts.append("种子的关注带出")
    elif "authors" in rc.channels:
        parts.append("发了相关笔记被发现")
    elif "users" in rc.channels:
        parts.append("账号资料匹配")
    return " · ".join(parts) or "相关账号"


def build_candidates(recalled: list[RecalledCandidate], existing_lookup: Callable[[str], int | None], platform: str) -> list[dict]:
    """召回结果 → 候选 dict(三层信息:数据 / 理由 / 匹配度),按综合分降序。纯函数,可测。"""
    out: list[dict] = []
    for rc in recalled:
        r = rc.result
        sig = _signals(rc, platform)
        out.append({
            "external_id": r.external_id,
            "display_name": r.display_name,
            "homepage_url": r.homepage_url,
            "avatar_url": r.avatar_url,
            "description": r.description,
            "follower_count": r.follower_count or 0,
            "follower_known": bool(getattr(r, "follower_known", True)),
            "is_personal": sig.is_personal,
            "score": composite_score(sig),
            "reason": _reason_line(rc),
            "matched": [lbl for lbl, _ in rc.matched],
            "from_seed": rc.from_seed,
            "existing_blogger_id": existing_lookup(r.external_id),
        })
    out.sort(key=lambda c: c["score"], reverse=True)
    return out


def selected_domains(session: BenchmarkDiscoverySession) -> list[WeightedDomain]:
    dirs = [d for d in session.directions if d.get("selected")]
    if not dirs:  # 没有选中的方向就退回原始领域
        return [WeightedDomain(label=str(d), weight=60.0) for d in session.intent.get("domains", []) if str(d).strip()]
    return [WeightedDomain(label=str(d.get("label", "")).strip(), weight=float(d.get("weight", 50)))
            for d in dirs if str(d.get("label", "")).strip()]


def _touch(session: BenchmarkDiscoverySession, settings: Settings) -> None:
    hours = int(getattr(settings, "discovery_session_ttl_hours", 2) or 2)
    session.expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)


def _existing_lookup(db: Session, tenant_id: int, platform: str, ext_ids: list[str]) -> dict[str, int]:
    if not ext_ids:
        return {}
    rows = db.scalars(
        select(BloggerProfile).where(
            BloggerProfile.tenant_id == tenant_id, BloggerProfile.platform == platform,
            BloggerProfile.external_id.in_([e for e in ext_ids if e]),
        )
    )
    return {b.external_id: b.id for b in rows if b.external_id}


def _pages_for_weight(base_pages: int, weight: float) -> int:
    """方向权重越高,翻得越深(让权重真影响召回深度)。weight 0→0.5×,100→1.5×。"""
    return max(1, min(base_pages + 1, round(base_pages * (0.5 + weight / 100.0))))


def start_session(
    db: Session, settings: Settings, tenant_id: int, platform: str, domains: list[str], my_account_id: int | None = None
) -> BenchmarkDiscoverySession:
    """入口:存意图、扩方向(LLM+兜底);可选「我的账号」直接进种子列。落在 workspace,候选先空。"""
    clean = [d.strip() for d in domains if d.strip()]
    if not clean:
        raise ValueError("请至少填写一个领域")
    dirs = expand_directions(settings, clean, max_directions=int(getattr(settings, "discovery_directions_max", 10)))

    seeds: list[dict] = []
    if my_account_id is not None:
        acc = db.get(BloggerProfile, my_account_id)
        if acc is not None and acc.tenant_id == tenant_id:
            seeds = [{
                "external_id": acc.external_id or f"acct-{acc.id}",
                "display_name": acc.display_name or "我的账号",
                "homepage_url": acc.homepage_url or "",
                "avatar_url": acc.avatar_url or "",
                "description": acc.description or "",
                "follower_count": acc.follower_count or 0,
                "follower_known": True, "is_personal": True, "is_mine": True,
                "score": 0, "reason": "你选的种子账号", "matched": [], "from_seed": False,
                "existing_blogger_id": acc.id,
            }]

    session = BenchmarkDiscoverySession(
        tenant_id=tenant_id, platform=platform, stage="workspace", status="active", round=0,
        my_account_id=my_account_id,
        intent_json=json.dumps({"domains": clean, "my_account_id": my_account_id}, ensure_ascii=False),
        directions_json=json.dumps([{"label": d.label, "weight": d.weight, "reason": d.reason, "selected": d.selected}
                                    for d in dirs], ensure_ascii=False),
        seeds_json=json.dumps(seeds, ensure_ascii=False),
        message="方向已就绪，点「继续找候选」开始",
    )
    _touch(session, settings)
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("泛搜索·新会话 会话=%s 平台=%s 领域=%s 种子账号=%s 扩展出%d个方向",
                session.id, platform, clean, my_account_id, len(dirs))
    return session


def update_directions(
    db: Session, settings: Settings, session: BenchmarkDiscoverySession,
    directions: list[dict] | None = None, add_domains: list[str] | None = None,
) -> None:
    """调方向:应用勾选/权重 + 可选新增领域(LLM 顺手再扩)。不重置任何列表。"""
    by_label = {d.get("label"): d for d in session.directions}
    for d in directions or []:
        label = str(d.get("label", "")).strip()
        if not label:
            continue
        try:
            weight = max(0.0, min(100.0, float(d.get("weight", 50))))
        except (TypeError, ValueError):
            weight = 50.0
        cur = by_label.get(label, {"label": label, "reason": ""})
        cur.update({"label": label, "weight": round(weight, 1),
                    "reason": str(d.get("reason", cur.get("reason", ""))), "selected": bool(d.get("selected", True))})
        by_label[label] = cur

    for nd in add_domains or []:
        nd = nd.strip()
        if not nd:
            continue
        for ex in expand_directions(settings, [nd], max_directions=4):
            if ex.label not in by_label:
                by_label[ex.label] = {"label": ex.label, "weight": ex.weight, "reason": ex.reason, "selected": True}

    session.directions_json = json.dumps(list(by_label.values()), ensure_ascii=False)
    _touch(session, settings)
    db.commit()
    logger.info("泛搜索·调方向 会话=%s 现有方向%d个(新增领域=%s)", session.id, len(by_label), add_domains or [])


def _gather_seed_following(
    session: BenchmarkDiscoverySession, settings: Settings,
    following_fn: Callable[[str], list[BloggerSearchResult]], on_progress: Callable[[str, str], None] | None,
) -> list[BloggerSearchResult]:
    """C 路:拉每个种子的关注列表,去掉机构号(找相似要的是同行个人号)。"""
    platform = session.platform
    seed_cap = int(getattr(settings, "discovery_seed_cap", 3) or 3)
    out: list[BloggerSearchResult] = []
    for seed in session.seeds[:seed_cap]:
        uid = str(seed.get("external_id", "")).strip()
        if not uid or uid.startswith("acct-"):  # 没有真实平台 id 的拉不了关注
            continue
        kept = [r for r in (following_fn(uid) or [])
                if not is_institution_account(platform, r.display_name, r.description, r.raw)]
        out.extend(kept)
        logger.info("泛搜索·按种子找 种子=「%s」 关注里筛出%d个", seed.get("display_name", ""), len(kept))
        if on_progress is not None:
            on_progress(f"种子「{seed.get('display_name', '')}」", f"关注里筛出 {len(kept)} 个")
    return out


def run_recall(
    db: Session, settings: Settings, session: BenchmarkDiscoverySession, *,
    mode: str = "directions", users_fn=None, notes_fn=None, following_fn=None,
    on_progress: Callable[[str, str], None] | None = None,
) -> dict:
    """找候选:按方向(mode=directions)或按种子关注(mode=seed)召回,**追加**到候选池(去重),新结果置顶。"""
    platform = session.platform
    base_pages = int(getattr(settings, "discovery_search_pages", 2) or 2)
    cap = int(getattr(settings, "discovery_candidate_cap", 12) or 12)
    pool_cap = int(getattr(settings, "discovery_pool_cap", 60) or 60)
    domains = selected_domains(session)
    weight_by = {d.label: d.weight for d in domains}

    if users_fn is None:
        def users_fn(kw: str) -> list[BloggerSearchResult]:
            pages = _pages_for_weight(base_pages, weight_by.get(kw, 50.0))
            acc: list[BloggerSearchResult] = []
            for p in range(1, pages + 1):
                acc.extend(search_bloggers(settings, platform, kw, p))
            return acc
    if notes_fn is None:
        def notes_fn(kw: str) -> list[BloggerSearchResult]:
            return search_note_authors(settings, platform, kw)
    if following_fn is None:
        def following_fn(uid: str) -> list[BloggerSearchResult]:
            return get_user_following(settings, platform, uid, limit=int(getattr(settings, "discovery_following_cap", 60)))

    t0 = time.monotonic()
    logger.info("泛搜索·开跑召回 会话=%s 模式=%s 第%d轮 方向=%s cap=%d 已看过=%d",
                session.id, mode, session.round + 1, [(d.label, round(d.weight)) for d in domains], cap, len(session.seen))

    if mode == "seed":
        following = _gather_seed_following(session, settings, following_fn, on_progress)
        recalled = recall([], search_users_fn=users_fn, search_notes_authors_fn=notes_fn,
                          seed_following=following, cap=cap, exclude_ids=session.seen)
    else:
        def on_domain(label: str, n_users: int, n_authors: int) -> None:
            if on_progress is not None:
                on_progress(f"搜「{label}」", f"用户 {n_users} · 笔记作者 {n_authors}")
        recalled = recall(domains, search_users_fn=users_fn, search_notes_authors_fn=notes_fn,
                          seed_following=None, cap=cap, exclude_ids=session.seen, on_domain=on_domain)

    ext_ids = [rc.result.external_id for rc in recalled]
    existing = _existing_lookup(db, session.tenant_id, platform, ext_ids)
    fresh = build_candidates(recalled, lambda i: existing.get(i), platform)

    have = {c["external_id"] for c in session.candidates}
    added = [c for c in fresh if c["external_id"] not in have]
    pool = (added + session.candidates)[:pool_cap]  # 新结果置顶,池子封顶

    session.candidates_json = json.dumps(pool, ensure_ascii=False)
    session.seen_json = json.dumps(sorted(set(session.seen) | {c["external_id"] for c in pool}), ensure_ascii=False)
    session.round += 1
    dryup = len(added) < int(getattr(settings, "discovery_dryup_threshold", 3))
    session.message = f"本次新增 {len(added)} 个候选" + ("，不多了，换/加方向或换种子试试" if dryup else "")
    _touch(session, settings)
    db.commit()

    personal = sum(1 for c in added if c["is_personal"])
    top = "; ".join(f'{c["display_name"]}({c["score"]}分/{c["follower_count"]}粉)' for c in added[:5])
    logger.info("泛搜索·召回完成 会话=%s 模式=%s 新增=%d(个人号%d) 候选池=%d 用时%.1fs;Top: %s",
                session.id, mode, len(added), personal, len(pool), time.monotonic() - t0, top or "(无)")
    return {"added": len(added), "pool": len(pool), "mode": mode, "dryup": dryup}


def move_candidates(db: Session, settings: Settings, session: BenchmarkDiscoverySession, ids: list[str], dest: str) -> None:
    """候选 → 种子 / 已选。移出候选(不再回候选);种子受 cap 限,放不下的留在候选。"""
    by_id = {c["external_id"]: c for c in session.candidates}
    picked = [by_id[i] for i in ids if i in by_id]
    moved: set[str] = set()
    if dest == DEST_SEED:
        seeds = {s["external_id"]: s for s in session.seeds}
        cap = int(getattr(settings, "discovery_seed_cap", 3) or 3)
        for c in picked:
            if c["external_id"] in seeds or len(seeds) < cap:
                seeds[c["external_id"]] = c
                moved.add(c["external_id"])
        session.seeds_json = json.dumps(list(seeds.values()), ensure_ascii=False)
    else:  # DEST_SELECTED
        basket = {b["external_id"]: b for b in session.basket}
        for c in picked:
            basket[c["external_id"]] = c
            moved.add(c["external_id"])
        session.basket_json = json.dumps(list(basket.values()), ensure_ascii=False)
    session.candidates_json = json.dumps([c for c in session.candidates if c["external_id"] not in moved], ensure_ascii=False)
    _touch(session, settings)
    db.commit()
    logger.info("泛搜索·移动 会话=%s %d个→%s (篮子%d 种子%d)",
                session.id, len(moved), dest, len(session.basket), len(session.seeds))


def seed_to_selected(db: Session, settings: Settings, session: BenchmarkDiscoverySession, ids: list[str]) -> None:
    """种子 → 已选(复制,种子保留,因为它还要继续帮你找)。"""
    by_id = {s["external_id"]: s for s in session.seeds}
    basket = {b["external_id"]: b for b in session.basket}
    for i in ids:
        if i in by_id:
            basket[i] = by_id[i]
    session.basket_json = json.dumps(list(basket.values()), ensure_ascii=False)
    _touch(session, settings)
    db.commit()


def remove_from(db: Session, settings: Settings, session: BenchmarkDiscoverySession, ids: list[str], which: str) -> None:
    """从种子/已选里移除(移除即没了,不回候选;external_id 留在 seen,不会再被翻出来烦你)。"""
    drop = set(ids)
    if which == DEST_SEED:
        session.seeds_json = json.dumps([s for s in session.seeds if s["external_id"] not in drop], ensure_ascii=False)
    else:
        session.basket_json = json.dumps([b for b in session.basket if b["external_id"] not in drop], ensure_ascii=False)
    _touch(session, settings)
    db.commit()


def clear_candidates(db: Session, settings: Settings, session: BenchmarkDiscoverySession) -> None:
    """清空候选(只清候选,不动种子/已选)。"""
    session.candidates_json = "[]"
    session.message = "候选已清空，点「继续找候选」或「按种子找候选」重新拉"
    _touch(session, settings)
    db.commit()


def save_selected(db: Session, session: BenchmarkDiscoverySession) -> list[BloggerProfile]:
    """把已选列表存进对标库(已有则复用,幂等)。可随时存、增量存;存完会话仍可继续用。"""
    from app.blogger_distillation.service.crud import create_blogger

    created: list[BloggerProfile] = []
    new_basket: list[dict] = []
    niche = (session.intent.get("domains") or [""])[0]
    for c in session.basket:
        blogger = create_blogger(
            db, session.tenant_id, session.platform,
            external_id=c.get("external_id") or None,
            display_name=c.get("display_name", "") or "对标博主",
            homepage_url=c.get("homepage_url", ""),
            avatar_url=c.get("avatar_url", ""),
            follower_count=int(c.get("follower_count") or 0),
            niche=niche,
            description=c.get("description", ""),
            account_type="benchmark",
        )
        created.append(blogger)
        new_basket.append({**c, "existing_blogger_id": blogger.id})
    session.basket_json = json.dumps(new_basket, ensure_ascii=False)
    session.message = f"已保存 {len(created)} 个到对标库"
    db.commit()
    logger.info("泛搜索·保存 会话=%s 入库%d个对标博主", session.id, len(created))
    return created


def build_workspace(session: BenchmarkDiscoverySession) -> dict:
    """三列工作台的前端契约:方向 + 候选 / 种子 / 已选。"""
    return {
        "session_id": session.id,
        "platform": session.platform,
        "stage": session.stage,
        "status": session.status,
        "message": session.message,
        "round": session.round,
        "directions": [{"id": d.get("label"), **d} for d in session.directions],
        "candidates": session.candidates,
        "seeds": session.seeds,
        "selected": session.basket,
    }


def reap_expired_sessions(db: Session, now: datetime) -> int:
    """空闲过期的会话标 expired(等待发生在客户端,这里只清记录)。"""
    rows = list(db.scalars(
        select(BenchmarkDiscoverySession).where(BenchmarkDiscoverySession.status == "active")
    ))
    n = 0
    for s in rows:
        exp = s.expires_at
        if exp is None:
            continue
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            s.status = "expired"
            n += 1
    if n:
        db.commit()
    return n
