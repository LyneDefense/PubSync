from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.benchmark_discovery import engine as engine_mod
from app.benchmark_discovery.context import BenchmarkContext
from app.benchmark_discovery.engine import evaluate_candidate, popularity_score
from app.benchmark_discovery.service import _dedupe_cap, _recent_from_db, _score_one
from app.blogger_distillation.search import BloggerSearchResult
from app.database import Base
from app.models import BloggerPost, BloggerProfile, Tenant


@pytest.fixture
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    try:
        yield session
    finally:
        session.close()


def _result(**kw):
    base = dict(
        platform="xhs", external_id="x1", display_name="博主", homepage_url="h",
        avatar_url="", description="保险科普", follower_count=10000, raw={},
    )
    base.update(kw)
    return BloggerSearchResult(**base)


def _recent(likes, raw=None):
    return [SimpleNamespace(like_count=v, raw=raw or {}) for v in likes]


# —— 火爆度公式 ——
def test_popularity_follower_tiers():
    assert popularity_score(0, []) == 0.0
    assert 55 <= popularity_score(1000, []) <= 65  # 无互动 → 退回粉丝分(~60)
    assert popularity_score(100000, []) >= 95


def test_popularity_engagement_caps_at_5pct():
    # 互动率 5% 封顶满分,叠加粉丝分
    high = popularity_score(10000, [500, 500, 500])
    low = popularity_score(10000, [10, 10, 10])
    assert high > low


def test_popularity_no_likes_falls_back_to_follower():
    assert popularity_score(10000, []) == popularity_score(10000, [0, 0])


# —— 去重 + 截断 ——
def test_dedupe_cap():
    results = [_result(external_id="a"), _result(external_id="a"), _result(external_id="b"), _result(external_id="c")]
    out = _dedupe_cap(results, cap=2)
    assert [r.external_id for r in out] == ["a", "b"]


# —— 评估内核:有/无账号 ——
def test_evaluate_without_account_has_no_transferability(monkeypatch):
    monkeypatch.setattr(
        engine_mod, "create_json_response",
        lambda *a, **k: {"relevance": {"score": 80, "reason": "贴合"}, "learnability": {"score": 60, "reason": "可学"}, "summary": "推荐"},
    )
    ctx = BenchmarkContext(platform="xhs", niche="保险", my_account_profile="")
    score = evaluate_candidate(SimpleNamespace(), ctx, _result(), _recent([100, 120]))
    assert score.transferability is None
    assert score.relevance == 80 and score.learnability == 60
    assert score.reasons["summary"] == "推荐"
    assert 0 <= score.overall <= 100


def test_evaluate_with_account_sets_transferability(monkeypatch):
    monkeypatch.setattr(
        engine_mod, "create_json_response",
        lambda *a, **k: {
            "relevance": {"score": 90}, "learnability": {"score": 70},
            "transferability": {"score": 50}, "summary": "ok",
        },
    )
    ctx = BenchmarkContext(platform="xhs", niche="保险", my_account_profile="我的账号画像...")
    score = evaluate_candidate(SimpleNamespace(), ctx, _result(), _recent([100]))
    assert score.transferability == 50


def test_evaluate_llm_failure_degrades_gracefully(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(engine_mod, "create_json_response", boom)
    ctx = BenchmarkContext(platform="xhs", niche="保险")
    score = evaluate_candidate(SimpleNamespace(), ctx, _result(), _recent([100]))
    assert score.relevance == 0 and "失败" in score.reasons["summary"]
    assert score.popularity > 0  # 火爆度纯规则,不受 LLM 影响


# —— 复用已采:已在库的博主不触发 live 取数 ——
def test_score_one_reuses_db_and_skips_live(db, monkeypatch):
    db.add(Tenant(id=1, name="T", slug="t"))
    db.add(BloggerProfile(id=1, tenant_id=1, platform="xhs", account_type="benchmark", external_id="x1", display_name="博主", homepage_url="h", sample_count=2))
    for i in range(2):
        db.add(BloggerPost(tenant_id=1, blogger_id=1, platform="xhs", external_id=f"e{i}", title=f"标题{i}", like_count=50, status="active"))
    db.commit()

    recent = _recent_from_db(db, 1, 1, 12)
    assert len(recent) == 2 and recent[0].like_count == 50

    def fail_live(*a, **k):
        raise AssertionError("已采过的博主不应再 live 取数")

    monkeypatch.setattr("app.benchmark_discovery.service._fetch_recent_live", fail_live)
    monkeypatch.setattr(
        engine_mod, "create_json_response",
        lambda *a, **k: {"relevance": {"score": 70}, "learnability": {"score": 70}, "summary": "s"},
    )
    ctx = BenchmarkContext(platform="xhs", niche="保险")
    score = _score_one(db, SimpleNamespace(), ctx, 1, "xhs", _result(external_id="x1"))
    assert score.existing_blogger_id == 1
