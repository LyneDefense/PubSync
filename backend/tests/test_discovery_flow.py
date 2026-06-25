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


def test_full_flow_intent_to_checkout(db):
    settings = Settings()
    # S1→S2
    sess = flow.start_session(db, settings, 1, "xhs", ["香港保险"])
    assert sess.stage == "confirm_directions"
    assert [d["label"] for d in sess.directions] == ["储蓄险科普", "香港身份"]
    assert sess.expires_at is not None

    # S2 提交方向
    flow.submit_directions(db, settings, sess, [{"label": "储蓄险科普", "weight": 90, "selected": True}])

    # S3 召回(注入通道:A 路给个人号 + 机构号,B 路给娜姐)
    # 同粉丝量级下,机构号(×0.9 降权)应排在个人号之后。
    users = {"储蓄险科普": [_r("org1", "保险品牌官方", 8000), _r("p1", "理财小王", 8000)]}
    notes = {"储蓄险科普": [_r("na", "保险经纪人娜姐", 12000)]}
    flow.run_recall(db, settings, sess,
                    users_fn=lambda kw: users.get(kw, []), notes_fn=lambda kw: notes.get(kw, []))
    assert sess.stage == "review_candidates" and sess.round == 1
    ids = [c["external_id"] for c in sess.candidates]
    assert "na" in ids and "p1" in ids and "org1" in ids
    # 个人号应排在机构号前(机构降权)
    assert ids.index("p1") < ids.index("org1")

    # 待办含固定选项 + 推荐
    todo = flow.build_todo(sess, recommended=flow.recommend_next(sess, has_seed_picks=False))
    assert {o["id"] for o in todo["options"]} == set(flow.NEXT_OPTIONS)
    assert todo["recommended"]["option_id"] == "more"

    # S4 采用娜姐 + 选 p1 当种子 + 继续
    choice = flow.submit_review(db, settings, sess, adopt_ids=["na"], seed_ids=["p1"], choice="seed_more")
    assert choice == "seed_more"
    assert [b["external_id"] for b in sess.basket] == ["na"]
    assert [s["external_id"] for s in sess.seeds] == ["p1"]

    # 下一轮召回应排除已看过的(na/p1/org1)
    flow.run_recall(db, settings, sess,
                    users_fn=lambda kw: users.get(kw, []), notes_fn=lambda kw: notes.get(kw, []))
    assert sess.candidates == []  # 全被 seen 排除
    assert sess.round == 2

    # 结账入库
    created = flow.checkout(db, sess)
    assert len(created) == 1 and created[0].account_type == "benchmark"
    assert sess.stage == "done" and sess.status == "done"
    assert db.query(BloggerProfile).filter_by(external_id="na").count() == 1


def test_seed_cap_enforced(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["x"])
    sess.candidates_json = '[{"external_id":"a","display_name":"A"},{"external_id":"b","display_name":"B"},{"external_id":"c","display_name":"C"},{"external_id":"d","display_name":"D"}]'
    db.commit()
    flow.submit_review(db, settings, sess, adopt_ids=[], seed_ids=["a", "b", "c", "d"], choice="seed_more")
    assert len(sess.seeds) == 3  # discovery_seed_cap


def test_recommend_change_directions_when_empty(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["x"])
    # 无候选 → 推荐换方向
    rec = flow.recommend_next(sess, has_seed_picks=False)
    assert rec["option_id"] == "change_directions"


def test_reap_expired(db):
    settings = Settings()
    sess = flow.start_session(db, settings, 1, "xhs", ["x"])
    sess.expires_at = NOW - timedelta(hours=1)
    db.commit()
    n = flow.reap_expired_sessions(db, NOW)
    assert n == 1
    assert db.get(BenchmarkDiscoverySession, sess.id).status == "expired"
