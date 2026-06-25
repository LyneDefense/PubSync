"""泛搜索（找对标）—— 漏斗式收窄。

两个入口都汇到同一个「候选 | 已选」工作台:
- 泛搜索(source=broad):领域 → **agent 迭代推细分角度,用户选够 target** → 按选中角度搜候选。
- 找相似(source=similar):从对标库挑 1+ 个博主 → 用其存量笔记取关键词 → 直接搜候选(无角度阶段)。

候选阶段只做「采用 / 不要」,不再有"种子"概念。等待用户发生在 HTTP 边界;空闲过期由清理任务标 expired。
确定性控制器,只在「推角度」节点借 agent(超时/失败走规则兜底)。召回(打 TikHub)由调用方放进异步任务。
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmark_discovery.querygen import suggest_subniches
from app.benchmark_discovery.ranking import CandidateSignals, composite_score
from app.benchmark_discovery.recall import RecalledCandidate, WeightedDomain, recall
from app.blogger_distillation.search import BloggerSearchResult, search_bloggers, search_note_authors
from app.config import Settings
from app.models import BloggerPost, BloggerProfile
from app.models.benchmark_discovery import BenchmarkDiscoverySession

logger = logging.getLogger(__name__)

INSTITUTION_HINTS = ("官方", "旗舰", "品牌", "有限公司", "集团", "机构", "客服", "商城", "专卖", "store", "official")
ENTERPRISE_VERIFY_HINTS = ("企业", "公司", "品牌", "官方", "商家", "enterprise", "company", "brand")
DEFAULT_ANGLE_WEIGHT = 80.0  # 选中的细分角度统一给这个权重(喂打分的命中相关度)


def is_institution_account(platform: str, name: str, desc: str, raw: dict | None) -> bool:
    """是不是机构/企业号。优先用平台认证标识(最准),取不到再退回关键词。"""
    raw = raw or {}
    if platform == "xhs":
        vt = raw.get("red_official_verify_type")
        if isinstance(vt, (int, float)) and int(vt) >= 2:
            return True
    else:
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
    r = rc.result
    return CandidateSignals(
        external_id=r.external_id,
        follower_count=r.follower_count or 0,
        like_samples=[],
        is_personal=not is_institution_account(platform, r.display_name, r.description, r.raw),
        matched_weight=min(100.0, sum(w for _, w in rc.matched)),
        popularity_known=bool(getattr(r, "follower_known", True)),
    )


def _reason_line(rc: RecalledCandidate) -> str:
    parts: list[str] = []
    if rc.matched:
        parts.append("命中" + "".join(f"「{lbl}」" for lbl, _ in rc.matched[:3]))
    if "authors" in rc.channels:
        parts.append("发了相关笔记")
    elif "users" in rc.channels:
        parts.append("账号资料匹配")
    return " · ".join(parts) or "相关账号"


def build_candidates(recalled: list[RecalledCandidate], existing_lookup: Callable[[str], int | None], platform: str) -> list[dict]:
    """召回结果 → 候选 dict(数据/理由/匹配度),按综合分降序。"""
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
            "existing_blogger_id": existing_lookup(r.external_id),
        })
    out.sort(key=lambda c: c["score"], reverse=True)
    return out


def selected_domains(session: BenchmarkDiscoverySession) -> list[WeightedDomain]:
    """选中(且未被排除)的细分角度 → 搜索关键词。"""
    out = []
    for d in session.directions:
        if d.get("selected") and not d.get("rejected") and str(d.get("label", "")).strip():
            out.append(WeightedDomain(label=str(d["label"]).strip(), weight=DEFAULT_ANGLE_WEIGHT))
    return out


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


def _intent(session: BenchmarkDiscoverySession) -> dict:
    return session.intent if isinstance(session.intent, dict) else {}


def _set_intent(session: BenchmarkDiscoverySession, **changes) -> None:
    data = _intent(session)
    data.update(changes)
    session.intent_json = json.dumps(data, ensure_ascii=False)


# —— 入口:泛搜索(broad) ——
def start_broad(db: Session, settings: Settings, tenant_id: int, platform: str, domains: list[str]) -> BenchmarkDiscoverySession:
    """领域 → 推第一批细分角度,停在 choose_angles 等用户选。"""
    clean = [d.strip() for d in domains if d.strip()]
    if not clean:
        raise ValueError("请至少填写一个领域")
    batch = int(getattr(settings, "discovery_angle_batch", 4) or 4)
    subs = suggest_subniches(settings, clean, n=batch)
    angles = [{"label": s.label, "reason": s.reason, "selected": False, "rejected": False} for s in subs]
    session = BenchmarkDiscoverySession(
        tenant_id=tenant_id, platform=platform, stage="choose_angles", status="active", round=0,
        intent_json=json.dumps({"domains": clean, "source": "broad", "angle_rounds": 1}, ensure_ascii=False),
        directions_json=json.dumps(angles, ensure_ascii=False),
        message="先选几个细分角度,系统会照着找",
    )
    _touch(session, settings)
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("泛搜索·新会话(broad) 会话=%s 领域=%s 首批角度=%d", session.id, clean, len(angles))
    return session


def angle_op(db: Session, settings: Settings, session: BenchmarkDiscoverySession, op: str, labels: list[str]) -> None:
    """角度收窄:toggle 选/取消、reject 排除、propose 再推一批、begin 开始搜。"""
    pool = session.directions
    by_label = {d.get("label"): d for d in pool}
    target = int(getattr(settings, "discovery_angle_target", 3) or 3)

    if op == "toggle":
        for lbl in labels:
            d = by_label.get(lbl)
            if d and not d.get("rejected"):
                d["selected"] = not d.get("selected")
    elif op == "reject":
        for lbl in labels:
            d = by_label.get(lbl)
            if d:
                d["rejected"] = True
                d["selected"] = False
    elif op == "propose":
        rounds = int(_intent(session).get("angle_rounds", 1))
        max_rounds = int(getattr(settings, "discovery_angle_max_rounds", 4) or 4)
        if rounds >= max_rounds:
            session.message = "角度差不多了,用选中的开始搜吧"
        else:
            selected = [d["label"] for d in pool if d.get("selected")]
            rejected = [d["label"] for d in pool if d.get("rejected")]
            shown = [d["label"] for d in pool]
            subs = suggest_subniches(settings, _intent(session).get("domains", []),
                                     selected=selected, rejected=rejected, shown=shown,
                                     n=int(getattr(settings, "discovery_angle_batch", 4) or 4))
            for s in subs:
                if s.label not in by_label:
                    pool.append({"label": s.label, "reason": s.reason, "selected": False, "rejected": False})
            _set_intent(session, angle_rounds=rounds + 1)
            session.message = "又推了几个角度,挑你想做的"
        session.directions_json = json.dumps(pool, ensure_ascii=False)
        _touch(session, settings)
        db.commit()
        return
    elif op == "begin":
        if not any(d.get("selected") and not d.get("rejected") for d in pool):
            raise ValueError("先选至少一个细分角度")
        session.stage = "workspace"
        n_sel = sum(1 for d in pool if d.get("selected") and not d.get("rejected"))
        session.message = (f"选多了({n_sel}个)可能搜得杂,但先按这些找" if n_sel > target
                           else "开始按选中的角度找候选")

    session.directions_json = json.dumps(pool, ensure_ascii=False)
    _touch(session, settings)
    db.commit()


# —— 入口:找相似(similar) ——
def derive_similar_keywords(db: Session, tenant_id: int, platform: str, blogger_ids: list[int]) -> tuple[list[str], list[str]]:
    """从对标库博主的存量笔记取关键词(领域 + 高频话题标签)。返回 (关键词, 参照博主名)。"""
    bloggers = list(db.scalars(select(BloggerProfile).where(
        BloggerProfile.tenant_id == tenant_id, BloggerProfile.platform == platform,
        BloggerProfile.id.in_(blogger_ids or []),
    )))
    names = [b.display_name for b in bloggers if b.display_name]
    keywords: list[str] = []
    for b in bloggers:
        if b.niche and b.niche.strip():
            keywords.append(b.niche.strip())
    tag_counter: Counter[str] = Counter()
    if bloggers:
        posts = db.scalars(select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id.in_([b.id for b in bloggers]),
        ).limit(200))
        for p in posts:
            try:
                tags = json.loads(p.hashtags_json or "[]")
            except (json.JSONDecodeError, TypeError):
                tags = []
            for t in tags:
                if isinstance(t, str) and t.strip():
                    tag_counter[t.strip().lstrip("#")] += 1
    keywords.extend([t for t, _ in tag_counter.most_common(5)])
    # 去重保序 + 兜底用博主名
    seen, uniq = set(), []
    for k in keywords + names:
        if k and k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq[:6], names


def start_similar(db: Session, settings: Settings, tenant_id: int, platform: str, blogger_ids: list[int]) -> BenchmarkDiscoverySession:
    """从对标库博主取关键词,直接进 workspace(无角度阶段)。"""
    keywords, names = derive_similar_keywords(db, tenant_id, platform, blogger_ids)
    if not keywords:
        raise ValueError("选中的博主还没有可用的笔记/领域信息，先采集一下再找相似")
    angles = [{"label": k, "reason": "来自你已有对标的内容", "selected": True, "rejected": False} for k in keywords]
    session = BenchmarkDiscoverySession(
        tenant_id=tenant_id, platform=platform, stage="workspace", status="active", round=0,
        intent_json=json.dumps({"domains": keywords, "source": "similar", "basis_names": names,
                                "basis_blogger_ids": blogger_ids}, ensure_ascii=False),
        directions_json=json.dumps(angles, ensure_ascii=False),
        message=f"按「{('、'.join(names))[:30]}」的内容找同类",
    )
    _touch(session, settings)
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("找相似·新会话 会话=%s 参照=%s 关键词=%s", session.id, names, keywords)
    return session


def _pages_for_weight(base_pages: int, weight: float) -> int:
    return max(1, min(base_pages + 1, round(base_pages * (0.5 + weight / 100.0))))


def run_recall(
    db: Session, settings: Settings, session: BenchmarkDiscoverySession, *,
    users_fn=None, notes_fn=None, on_progress: Callable[[str, str], None] | None = None,
) -> dict:
    """按选中角度/关键词召回,**追加**到候选池(去重、新结果置顶)。"""
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

    t0 = time.monotonic()
    logger.info("泛搜索·开跑召回 会话=%s 来源=%s 第%d轮 角度=%s",
                session.id, _intent(session).get("source"), session.round + 1, [d.label for d in domains])

    def on_domain(label: str, n_users: int, n_authors: int) -> None:
        if on_progress is not None:
            on_progress(f"搜「{label}」", f"用户 {n_users} · 笔记作者 {n_authors}")

    recalled = recall(domains, search_users_fn=users_fn, search_notes_authors_fn=notes_fn,
                      cap=cap, exclude_ids=session.seen, on_domain=on_domain)
    existing = _existing_lookup(db, session.tenant_id, platform, [rc.result.external_id for rc in recalled])
    fresh = build_candidates(recalled, lambda i: existing.get(i), platform)

    have = {c["external_id"] for c in session.candidates}
    added = [c for c in fresh if c["external_id"] not in have]
    pool = (added + session.candidates)[:pool_cap]

    session.candidates_json = json.dumps(pool, ensure_ascii=False)
    session.seen_json = json.dumps(sorted(set(session.seen) | {c["external_id"] for c in pool}), ensure_ascii=False)
    session.round += 1
    dryup = len(added) < int(getattr(settings, "discovery_dryup_threshold", 3))
    session.message = f"本次新增 {len(added)} 个候选" + ("，不多了，换/加角度试试" if dryup else "")
    _touch(session, settings)
    db.commit()
    top = "; ".join(f'{c["display_name"]}({c["score"]}分)' for c in added[:5])
    logger.info("泛搜索·召回完成 会话=%s 新增=%d 候选池=%d 用时%.1fs;Top: %s",
                session.id, len(added), len(pool), time.monotonic() - t0, top or "(无)")
    return {"added": len(added), "pool": len(pool), "dryup": dryup}


def adopt_candidates(db: Session, settings: Settings, session: BenchmarkDiscoverySession, ids: list[str]) -> None:
    """采用:候选 → 已选(移出候选)。"""
    by_id = {c["external_id"]: c for c in session.candidates}
    basket = {b["external_id"]: b for b in session.basket}
    take = set()
    for i in ids:
        if i in by_id:
            basket[i] = by_id[i]
            take.add(i)
    session.basket_json = json.dumps(list(basket.values()), ensure_ascii=False)
    session.candidates_json = json.dumps([c for c in session.candidates if c["external_id"] not in take], ensure_ascii=False)
    _touch(session, settings)
    db.commit()


def dismiss_candidates(db: Session, settings: Settings, session: BenchmarkDiscoverySession, ids: list[str]) -> None:
    """不要:从候选移除(已在 seen 里,不会再被翻出来)。"""
    drop = set(ids)
    session.candidates_json = json.dumps([c for c in session.candidates if c["external_id"] not in drop], ensure_ascii=False)
    _touch(session, settings)
    db.commit()


def remove_selected(db: Session, settings: Settings, session: BenchmarkDiscoverySession, ids: list[str]) -> None:
    drop = set(ids)
    session.basket_json = json.dumps([b for b in session.basket if b["external_id"] not in drop], ensure_ascii=False)
    _touch(session, settings)
    db.commit()


def clear_candidates(db: Session, settings: Settings, session: BenchmarkDiscoverySession) -> None:
    session.candidates_json = "[]"
    session.message = "候选已清空，点「再找一批」重新拉"
    _touch(session, settings)
    db.commit()


def save_selected(db: Session, session: BenchmarkDiscoverySession) -> list[BloggerProfile]:
    """把已选列表存进对标库(已有则复用,幂等)。可随时存、增量存。"""
    from app.blogger_distillation.service.crud import create_blogger

    created: list[BloggerProfile] = []
    new_basket: list[dict] = []
    niche = (_intent(session).get("domains") or [""])[0]
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
    logger.info("泛搜索·保存 会话=%s 入库%d个", session.id, len(created))
    return created


def build_workspace(session: BenchmarkDiscoverySession, settings: Settings | None = None) -> dict:
    """前端契约。choose_angles 阶段渲染角度选择;workspace 阶段渲染候选|已选。"""
    intent = _intent(session)
    target = int(getattr(settings, "discovery_angle_target", 3) or 3) if settings else 3
    selected_n = sum(1 for d in session.directions if d.get("selected") and not d.get("rejected"))
    return {
        "session_id": session.id,
        "platform": session.platform,
        "source": intent.get("source", "broad"),
        "stage": session.stage,
        "status": session.status,
        "message": session.message,
        "round": session.round,
        "angle_target": target,
        "selected_angles": selected_n,
        "angles": [d for d in session.directions if not d.get("rejected")],
        "candidates": session.candidates,
        "selected": session.basket,
    }


def reap_expired_sessions(db: Session, now: datetime) -> int:
    rows = list(db.scalars(select(BenchmarkDiscoverySession).where(BenchmarkDiscoverySession.status == "active")))
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
