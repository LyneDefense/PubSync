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
from app.models import BloggerPost, BloggerProfile, Tenant
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
    # suggest_subniches 读 data["subniches"]
    monkeypatch.setattr(querygen, "create_json_response", lambda s, p: {"subniches": [
        {"label": "储蓄险测评", "reason": "a"}, {"label": "理赔案例", "reason": "b"},
        {"label": "投保科普", "reason": "c"}, {"label": "港漂身份", "reason": "d"},
    ]})


def _recall(db, settings, sess, users, notes=None):
    flow.run_recall(db, settings, sess, users_fn=lambda kw: users.get(kw, []),
                    notes_fn=lambda kw: (notes or {}).get(kw, []))


def test_broad_angle_stage(db):
    settings = Settings()
    sess = flow.start_broad(db, settings, 1, "xhs", ["香港保险"])
    assert sess.stage == "choose_angles"
    assert [d["label"] for d in sess.directions] == ["储蓄险测评", "理赔案例", "投保科普", "港漂身份"]
    assert all(not d["selected"] for d in sess.directions)  # 默认都不选,用户来挑

    # 选两个角度
    flow.angle_op(db, settings, sess, "toggle", ["储蓄险测评", "理赔案例"])
    assert [d.label for d in flow.selected_domains(sess)] == ["储蓄险测评", "理赔案例"]

    # 排除一个
    flow.angle_op(db, settings, sess, "reject", ["港漂身份"])
    assert any(d["label"] == "港漂身份" and d["rejected"] for d in sess.directions)

    # 开始搜 → 进 workspace
    flow.angle_op(db, settings, sess, "begin", [])
    assert sess.stage == "workspace"


def test_begin_requires_selection(db):
    settings = Settings()
    sess = flow.start_broad(db, settings, 1, "xhs", ["香港保险"])
    with pytest.raises(ValueError):
        flow.angle_op(db, settings, sess, "begin", [])


def test_propose_more_angles_and_round_cap(db):
    settings = Settings()
    sess = flow.start_broad(db, settings, 1, "xhs", ["香港保险"])
    before = len(sess.directions)
    flow.angle_op(db, settings, sess, "propose", [])
    assert len(sess.directions) > before          # 追加了新角度(LLM 重复 → 规则兜底补新的)
    assert sess.intent.get("angle_rounds") == 2


def test_recall_and_candidate_shape(db):
    settings = Settings()
    sess = flow.start_broad(db, settings, 1, "xhs", ["香港保险"])
    flow.angle_op(db, settings, sess, "toggle", ["储蓄险测评"])
    flow.angle_op(db, settings, sess, "begin", [])

    users = {"储蓄险测评": [_r("org1", "保险品牌官方", 8000), _r("p1", "理财小王", 8000)]}
    notes = {"储蓄险测评": [_r("na", "保险经纪人娜姐", 12000)]}
    _recall(db, settings, sess, users, notes)

    cands = {c["external_id"]: c for c in sess.candidates}
    assert set(cands) == {"org1", "p1", "na"}
    ids = [c["external_id"] for c in sess.candidates]
    assert ids.index("p1") < ids.index("org1")           # 个人号在机构号前
    assert "储蓄险测评" in cands["na"]["matched"] and cands["na"]["score"] > 0


def test_adopt_dismiss_save(db):
    settings = Settings()
    sess = flow.start_broad(db, settings, 1, "xhs", ["香港保险"])
    flow.angle_op(db, settings, sess, "toggle", ["储蓄险测评"])
    flow.angle_op(db, settings, sess, "begin", [])
    _recall(db, settings, sess, {"储蓄险测评": [_r("a", "甲", 8000), _r("b", "乙", 7000), _r("c", "丙", 6000)]})

    flow.adopt_candidates(db, settings, sess, ["a"])
    assert "a" in {x["external_id"] for x in sess.basket}
    assert "a" not in {c["external_id"] for c in sess.candidates}

    flow.dismiss_candidates(db, settings, sess, ["b"])
    assert "b" not in {c["external_id"] for c in sess.candidates}

    created = flow.save_selected(db, sess)
    assert [bl.external_id for bl in created] == ["a"]
    assert sess.status == "active"
    assert db.query(BloggerProfile).filter_by(external_id="a", account_type="benchmark").count() == 1
    # 再召回 b 不会回来(在 seen 里)
    _recall(db, settings, sess, {"储蓄险测评": [_r("b", "乙", 7000)]})
    assert "b" not in {c["external_id"] for c in sess.candidates}


def test_recall_appends_and_dedupes(db):
    settings = Settings()
    sess = flow.start_broad(db, settings, 1, "xhs", ["香港保险"])
    flow.angle_op(db, settings, sess, "toggle", ["储蓄险测评"])
    flow.angle_op(db, settings, sess, "begin", [])
    _recall(db, settings, sess, {"储蓄险测评": [_r("p1", "甲", 8000)]})
    _recall(db, settings, sess, {"储蓄险测评": [_r("p1", "甲", 8000), _r("p2", "乙", 9000)]})
    assert [c["external_id"] for c in sess.candidates] == ["p2", "p1"]   # 新结果置顶、去重


def test_similar_from_benchmark_bloggers(db):
    settings = Settings()
    b = BloggerProfile(tenant_id=1, platform="xhs", external_id="bm1", display_name="娜姐",
                       homepage_url="", avatar_url="", niche="香港保险", description="", account_type="benchmark")
    db.add(b)
    db.commit()
    db.add(BloggerPost(tenant_id=1, blogger_id=b.id, platform="xhs", external_id="n1",
                       title="储蓄险测评", hashtags_json='["储蓄险", "港险"]'))
    db.commit()

    keywords, names = flow.derive_similar_keywords(db, 1, "xhs", [b.id])
    assert "香港保险" in keywords and "储蓄险" in keywords
    assert names == ["娜姐"]

    sess = flow.start_similar(db, settings, 1, "xhs", [b.id])
    assert sess.stage == "workspace" and sess.intent["source"] == "similar"
    assert {d.label for d in flow.selected_domains(sess)} >= {"香港保险", "储蓄险"}


def test_reap_expired(db):
    settings = Settings()
    sess = flow.start_broad(db, settings, 1, "xhs", ["x"])
    sess.expires_at = NOW - timedelta(hours=1)
    db.commit()
    assert flow.reap_expired_sessions(db, NOW) == 1
    assert db.get(BenchmarkDiscoverySession, sess.id).status == "expired"
