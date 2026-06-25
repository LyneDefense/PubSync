"""泛搜索（找对标）状态机：确定性控制器,只在节点内借 LLM(扩方向),其余规则化,处处有兜底。

节点: intent → confirm_directions → review_candidates(循环) → done。
等待用户发生在 HTTP 边界;重活(召回)由调用方放进异步任务,这里 run_recall 是可直接调用/可测的纯逻辑+落库。
S4「下一步」选项固定,推荐(预选)用规则给(LLM 版可后续替换),人确认。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmark_discovery.querygen import expand_directions
from app.benchmark_discovery.ranking import CandidateSignals, composite_score
from app.benchmark_discovery.recall import WeightedDomain, recall
from app.blogger_distillation.search import BloggerSearchResult, search_bloggers, search_note_authors
from app.config import Settings
from app.models import BloggerProfile
from app.models.benchmark_discovery import BenchmarkDiscoverySession

# S4 固定选项(不靠 AI 生成)。控制器按上下文裁剪(如没选种子就不出 seed_more)。
NEXT_OPTIONS = {
    "more": "继续找更多",
    "seed_more": "以选中的当种子，找更像的",
    "change_directions": "换/调方向",
    "finish": "完成，把选中的入库",
}
INSTITUTION_HINTS = ("官方", "旗舰", "品牌", "有限公司", "集团", "机构", "客服", "商城", "专卖", "store", "official")


def _is_personal(name: str, desc: str) -> bool:
    blob = f"{name} {desc}".lower()
    return not any(h.lower() in blob for h in INSTITUTION_HINTS)


def _signals(r: BloggerSearchResult) -> CandidateSignals:
    """从搜索结果拿到的客观信号(便宜,不额外取数);like 样本/活跃度 Phase2 再补。"""
    return CandidateSignals(
        external_id=r.external_id,
        follower_count=r.follower_count or 0,
        like_samples=[],
        is_personal=_is_personal(r.display_name, r.description),
    )


def selected_domains(session: BenchmarkDiscoverySession) -> list[WeightedDomain]:
    dirs = [d for d in session.directions if d.get("selected")]
    if not dirs:  # 没有选中的方向就退回原始领域
        return [WeightedDomain(label=d, weight=60.0) for d in session.intent.get("domains", []) if str(d).strip()]
    return [WeightedDomain(label=str(d.get("label", "")).strip(), weight=float(d.get("weight", 50)))
            for d in dirs if str(d.get("label", "")).strip()]


def build_candidates(results: list[BloggerSearchResult], existing_lookup=lambda _id: None) -> list[dict]:
    """搜索结果 → 候选 dict(带规则理由 + 综合分),按分降序。纯函数,可测。"""
    out: list[dict] = []
    for r in results:
        sig = _signals(r)
        score = composite_score(sig)
        reason = _reason_line(r, sig)
        out.append({
            "external_id": r.external_id,
            "display_name": r.display_name,
            "homepage_url": r.homepage_url,
            "avatar_url": r.avatar_url,
            "description": r.description,
            "follower_count": r.follower_count or 0,
            "is_personal": sig.is_personal,
            "score": score,
            "reason": reason,
            "existing_blogger_id": existing_lookup(r.external_id),
        })
    out.sort(key=lambda c: c["score"], reverse=True)
    return out


def _reason_line(r: BloggerSearchResult, sig: CandidateSignals) -> str:
    parts = [f"{r.follower_count or 0} 粉", "个人号" if sig.is_personal else "机构/泛号"]
    if r.description.strip():
        parts.insert(1, r.description.strip()[:24])
    return " · ".join(parts)


def _touch(session: BenchmarkDiscoverySession, settings: Settings) -> None:
    hours = int(getattr(settings, "discovery_session_ttl_hours", 2) or 2)
    session.expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)


def start_session(
    db: Session, settings: Settings, tenant_id: int, platform: str, domains: list[str], my_account_id: int | None = None
) -> BenchmarkDiscoverySession:
    """S1→S2:存意图、扩方向(LLM+兜底),停在 confirm_directions 等用户勾选。"""
    clean = [d.strip() for d in domains if d.strip()]
    if not clean:
        raise ValueError("请至少填写一个领域")
    dirs = expand_directions(settings, clean, max_directions=int(getattr(settings, "discovery_directions_max", 10)))
    session = BenchmarkDiscoverySession(
        tenant_id=tenant_id, platform=platform, stage="confirm_directions", status="active", round=0,
        my_account_id=my_account_id,
        intent_json=json.dumps({"domains": clean, "my_account_id": my_account_id}, ensure_ascii=False),
        directions_json=json.dumps([{"label": d.label, "weight": d.weight, "reason": d.reason, "selected": d.selected}
                                    for d in dirs], ensure_ascii=False),
        message="确认要搜的方向",
    )
    _touch(session, settings)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def submit_directions(db: Session, settings: Settings, session: BenchmarkDiscoverySession, directions: list[dict]) -> None:
    """保存用户勾选/调权重后的方向(只存;召回由调用方放进异步任务跑)。"""
    cleaned = []
    for d in directions:
        label = str(d.get("label", "")).strip()
        if not label:
            continue
        try:
            weight = max(0.0, min(100.0, float(d.get("weight", 50))))
        except (TypeError, ValueError):
            weight = 50.0
        cleaned.append({"label": label, "weight": round(weight, 1),
                        "reason": str(d.get("reason", "")), "selected": bool(d.get("selected", True))})
    if cleaned:
        session.directions_json = json.dumps(cleaned, ensure_ascii=False)
    _touch(session, settings)
    db.commit()


def run_recall(db: Session, settings: Settings, session: BenchmarkDiscoverySession, *, users_fn=None, notes_fn=None) -> None:
    """S3:三路召回 → 候选(带理由+分) → 写会话,stage=review_candidates。可注入通道便于测。"""
    platform = session.platform
    pages = int(getattr(settings, "discovery_search_pages", 2) or 2)
    cap = int(getattr(settings, "discovery_candidate_cap", 30) or 30)

    if users_fn is None:
        def users_fn(kw: str) -> list[BloggerSearchResult]:
            acc: list[BloggerSearchResult] = []
            for p in range(1, pages + 1):
                acc.extend(search_bloggers(settings, platform, kw, p))
            return acc
    if notes_fn is None:
        def notes_fn(kw: str) -> list[BloggerSearchResult]:
            return search_note_authors(settings, platform, kw)

    results = recall(
        selected_domains(session),
        search_users_fn=users_fn, search_notes_authors_fn=notes_fn,
        seed_following=None,  # C 路(种子关注)Phase 2
        cap=cap, exclude_ids=session.seen,
    )
    existing = _existing_lookup(db, session.tenant_id, platform, [r.external_id for r in results])
    candidates = build_candidates(results, existing_lookup=lambda i: existing.get(i))

    session.candidates_json = json.dumps(candidates, ensure_ascii=False)
    session.seen_json = json.dumps(sorted(set(session.seen) | {c["external_id"] for c in candidates}), ensure_ascii=False)
    session.round += 1
    session.stage = "review_candidates"
    session.message = f"第 {session.round} 轮：找到 {len(candidates)} 个候选" + (
        "，可能不多了，换/加方向或换种子试试" if len(candidates) < int(getattr(settings, "discovery_dryup_threshold", 3)) else ""
    )
    _touch(session, settings)
    db.commit()


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


def recommend_next(session: BenchmarkDiscoverySession, *, has_seed_picks: bool) -> dict | None:
    """S4 推荐下一步(规则版,预选+理由)。LLM 版可后续替换;失败/不确定就不预选。"""
    cands = session.candidates
    if not cands:
        return {"option_id": "change_directions", "reason": "这一批没找到合适的，建议换或加个方向"}
    if has_seed_picks:
        return {"option_id": "seed_more", "reason": "用你选的当种子，挖更多同类"}
    if len(session.basket) >= 5:
        return {"option_id": "finish", "reason": "篮子里够用了，可以入库了"}
    return {"option_id": "more", "reason": "还可以再多看一批"}


def build_todo(session: BenchmarkDiscoverySession, *, recommended: dict | None = None) -> dict:
    """按当前 stage 产出前端「待办」。confirm_directions / review_candidates / done。"""
    base = {"session_id": session.id, "stage": session.stage, "message": session.message,
            "round": session.round, "basket": session.basket, "seeds": session.seeds}
    if session.stage == "confirm_directions":
        base["directions"] = [{"id": d["label"], **d} for d in session.directions]
    elif session.stage == "review_candidates":
        opts = dict(NEXT_OPTIONS)
        base["candidates"] = session.candidates
        base["options"] = [{"id": k, "label": v} for k, v in opts.items()]
        base["recommended"] = recommended
        base["input"] = {"key": "refine", "placeholder": "补充要求，如 只要个人号 / 粉丝过万"}
    return base


def submit_review(
    db: Session, settings: Settings, session: BenchmarkDiscoverySession,
    adopt_ids: list[str], seed_ids: list[str], choice: str, text: str = "",
) -> str:
    """更新篮子/种子/筛选提示,返回路由 choice(more/seed_more/change_directions/finish)。"""
    by_id = {c["external_id"]: c for c in session.candidates}
    basket = {b["external_id"]: b for b in session.basket}
    for i in adopt_ids:
        if i in by_id:
            basket[i] = by_id[i]
    session.basket_json = json.dumps(list(basket.values()), ensure_ascii=False)

    seeds = {s["external_id"]: s for s in session.seeds}
    cap = int(getattr(settings, "discovery_seed_cap", 3) or 3)
    for i in seed_ids:
        if i in by_id and len(seeds) < cap:
            seeds[i] = by_id[i]
    session.seeds_json = json.dumps(list(seeds.values()), ensure_ascii=False)

    intent = session.intent
    if text.strip():
        intent["refine"] = text.strip()
        session.intent_json = json.dumps(intent, ensure_ascii=False)

    if choice == "change_directions":
        session.stage = "confirm_directions"
        session.message = "调整方向后再找"
    _touch(session, settings)
    db.commit()
    return choice if choice in NEXT_OPTIONS else "more"


def checkout(db: Session, session: BenchmarkDiscoverySession) -> list[BloggerProfile]:
    """把篮子里的号入对标库(已有则复用),会话置 done。"""
    from app.blogger_distillation.service.crud import create_blogger

    created: list[BloggerProfile] = []
    for c in session.basket:
        blogger = create_blogger(
            db, session.tenant_id, session.platform,
            external_id=c.get("external_id") or None,
            display_name=c.get("display_name", "") or "对标博主",
            homepage_url=c.get("homepage_url", ""),
            avatar_url=c.get("avatar_url", ""),
            follower_count=int(c.get("follower_count") or 0),
            niche=(session.intent.get("domains") or [""])[0],
            description=c.get("description", ""),
            account_type="benchmark",
        )
        created.append(blogger)
    session.stage = "done"
    session.status = "done"
    session.message = f"已入库 {len(created)} 个对标博主"
    db.commit()
    return created


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
