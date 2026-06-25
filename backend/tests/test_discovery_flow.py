from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.benchmark_discovery import flow, querygen
from app.config import Settings
from app.database import Base
from app.blogger_distillation.search import BloggerSearchResult
from app.models import BloggerProfile, Tenant
from app.models.benchmark_discovery import BenchmarkDiscoverySession

NOW = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Tenant(id=1, name="T", slug="t"))
    s.commit()
    try:
        yield s
    finally:
        s.close()


def _r(ext: str, name: str, followers: int = 5000, desc: str = "") -> BloggerSearchResult:
    return BloggerSearchResult(platform="xhs", external_id=ext, display_name=name,
                               homepage_url=f"h/{ext}", avatar_url="", description=desc, follower_count=followers, raw={})


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    monkeypatch.setattr(querygen, "create_json_response", lambda s, p: {"directions": [
        {"label": "储蓄险科普", "weight": 80}, {"label": "香港身份", "weight": 50},
    ]})


def _recall_dirs(db, settings, sess, users, notes):
    flow.run_recall(db, settings, sess, mode="directions",
                    users_fn=lambda kw: users.get(kw, []), notes_fn=lambda kw: notes.get(kw, []))


def test_start_recall_and_candidate_shape(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["香港保险"])
    assert sess.stage == "workspace"
    assert [d["label"] for d in sess.directions] == ["储蓄险科普", "香港身份"]

    # A 路给个人号 + 机构号(同粉丝量),B 路给娜姐(粉丝更高)
    users = {"储蓄险科普": [_r("org1", "保险品牌官方", 8000), _r("p1", "理财小王", 8000)]}
    notes = {"储蓄险科普": [_r("na", "保险经纪人娜姐", 12000)]}
    _recall_dirs(db, settings, sess, users, notes)

    cands = sess.candidates
    ids = [c["external_id"] for c in cands]
    assert set(ids) == {"na", "p1", "org1"}
    # 个人号排在机构号前(机构 ×0.9 降权);每个候选都带理由+分+命中方向
    assert ids.index("p1") < ids.index("org1")
    by = {c["external_id"]: c for c in cands}
    assert by["org1"]["is_personal"] is False and by["p1"]["is_personal"] is True
    assert "储蓄险科普" in by["na"]["matched"] and by["na"]["reason"]
    assert by["na"]["score"] > 0


def test_recall_appends_and_dedupes(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["香港保险"])
    users = {"储蓄险科普": [_r("p1", "小王", 8000)]}
    _recall_dirs(db, settings, sess, users, {})
    assert [c["external_id"] for c in sess.candidates] == ["p1"]
    # 再来一轮:p1 已 seen,不重复;新增 p2 置顶
    users2 = {"储蓄险科普": [_r("p1", "小王", 8000), _r("p2", "小李", 9000)]}
    _recall_dirs(db, settings, sess, users2, {})
    ids = [c["external_id"] for c in sess.candidates]
    assert ids == ["p2", "p1"] and sess.round == 2  # 新结果置顶、去重


def test_move_remove_and_save(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["香港保险"])
    _recall_dirs(db, settings, sess, {"储蓄险科普": [_r("a", "甲", 8000), _r("b", "乙", 7000), _r("c", "丙", 6000)]}, {})

    # 候选 → 种子(移出候选)
    flow.move_candidates(db, settings, sess, ["a"], flow.DEST_SEED)
    assert [s["external_id"] for s in sess.seeds] == ["a"]
    assert "a" not in {c["external_id"] for c in sess.candidates}
    # 种子 → 已选(复制,种子保留)
    flow.seed_to_selected(db, settings, sess, ["a"])
    assert "a" in {b["external_id"] for b in sess.basket}
    assert "a" in {s["external_id"] for s in sess.seeds}  # 仍在种子
    # 候选 → 已选
    flow.move_candidates(db, settings, sess, ["b"], flow.DEST_SELECTED)
    assert "b" not in {c["external_id"] for c in sess.candidates}

    # 保存入库(幂等),会话仍 active
    created = flow.save_selected(db, sess)
    assert {b.external_id for b in created} == {"a", "b"}
    assert sess.status == "active"
    assert db.query(BloggerProfile).filter_by(external_id="a", account_type="benchmark").count() == 1
    # 已选项标记 existing_blogger_id
    assert all(b.get("existing_blogger_id") for b in sess.basket)

    # 移除已选里的 b(不回候选)
    flow.remove_from(db, settings, sess, ["b"], flow.DEST_SELECTED)
    assert "b" not in {b["external_id"] for b in sess.basket}
    assert "b" not in {c["external_id"] for c in sess.candidates}


def test_seed_cap_enforced_on_move(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["x"])
    sess.candidates_json = ('[{"external_id":"a","display_name":"A","is_personal":true},'
                            '{"external_id":"b","display_name":"B","is_personal":true},'
                            '{"external_id":"c","display_name":"C","is_personal":true},'
                            '{"external_id":"d","display_name":"D","is_personal":true}]')
    db.commit()
    flow.move_candidates(db, settings, sess, ["a", "b", "c", "d"], flow.DEST_SEED)
    assert len(sess.seeds) == 3                       # discovery_seed_cap
    assert "d" in {c["external_id"] for c in sess.candidates}  # 放不下的留在候选


def test_seed_mode_uses_following_and_filters_institutions(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["香港保险"])
    # 先把 na 设成种子
    sess.candidates_json = '[{"external_id":"na","display_name":"娜姐","is_personal":true}]'
    db.commit()
    flow.move_candidates(db, settings, sess, ["na"], flow.DEST_SEED)

    following = {"na": [_r("peer1", "同行小美", 9000), _r("brandX", "某某保险官方", 50000)]}
    flow.run_recall(db, settings, sess, mode="seed", following_fn=lambda uid: following.get(uid, []))
    ids = {c["external_id"] for c in sess.candidates}
    assert "peer1" in ids          # 同行个人号进候选
    assert "brandX" not in ids     # 机构号被筛掉
    assert next(c for c in sess.candidates if c["external_id"] == "peer1")["from_seed"] is True


def test_clear_candidates(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["x"])
    _recall_dirs(db, settings, sess, {"储蓄险科普": [_r("a", "甲")]}, {})
    assert sess.candidates
    flow.clear_candidates(db, settings, sess)
    assert sess.candidates == []
    # 但 seen 仍保留(不会再翻出来)
    _recall_dirs(db, settings, sess, {"储蓄险科普": [_r("a", "甲")]}, {})
    assert sess.candidates == []


def test_update_directions_add_domain(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["香港保险"])
    flow.update_directions(db, settings, sess,
                           directions=[{"label": "储蓄险科普", "weight": 95, "selected": True}],
                           add_domains=["重疾险"])
    labels = {d["label"]: d for d in sess.directions}
    assert labels["储蓄险科普"]["weight"] == 95.0
    assert "储蓄险科普" in labels  # 原方向还在,没被重置


def test_my_account_becomes_seed(db):
    settings = Settings()
    acc = BloggerProfile(tenant_id=1, platform="xhs", external_id="me123", display_name="我的号",
                         homepage_url="", avatar_url="", niche="", description="", account_type="mine")
    db.add(acc)
    db.commit()
    sess = flow.start_session(db, settings, 1, "xhs", ["香港保险"], my_account_id=acc.id)
    assert [s["external_id"] for s in sess.seeds] == ["me123"]
    assert sess.seeds[0]["is_mine"] is True


def test_reap_expired(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["x"])
    sess.expires_at = NOW - timedelta(hours=1)
    db.commit()
    n = flow.reap_expired_sessions(db, NOW)
    assert n == 1
    assert db.get(BenchmarkDiscoverySession, sess.id).status == "expired"
