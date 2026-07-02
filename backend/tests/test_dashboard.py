from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.config import Settings
from app.dashboard.service import (
    build_account_dashboard,
    build_account_growth,
    build_overview,
    capture_account_snapshot,
    mark_package_published,
)
from app.database import Base
from app.models import AccountMetricSnapshot, BloggerPost, BloggerProfile, Tenant, XhsPublishPackage


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _settings() -> Settings:
    return Settings(
        dashboard_minutes_write_per_post=40,
        dashboard_minutes_ai_draft_per_post=10,
        dashboard_minutes_research_per_distill=30,
        dashboard_viral_multiplier=2.0,
    )


def _seed_tenant(db) -> None:
    db.add(Tenant(id=1, name="T", slug="t"))
    db.commit()


def test_overview_empty_tenant_does_not_crash(db):
    """没有任何数据(也没绑账号)时,overview 仍返回结构化零值。"""
    _seed_tenant(db)
    out = build_overview(db, _settings(), tenant_id=1)
    assert out["creation"] == {"created": 0, "published": 0, "conversion": 0.0}
    assert out["library"]["my_account_count"] == 0
    assert out["saved_minutes"] == 0
    assert {a["key"] for a in out["activities"]} >= {"blogger_collection", "xhs_package_draft"}


def test_overview_counts_creation_and_saved_time(db):
    _seed_tenant(db)
    db.add(BloggerProfile(id=10, tenant_id=1, platform="xhs", account_type="benchmark", display_name="大V", homepage_url="h"))
    db.add(BloggerProfile(id=20, tenant_id=1, platform="xhs", account_type="mine", display_name="我", homepage_url="h2"))
    db.flush()
    # 3 篇创作,1 篇标记已发布
    for i in range(3):
        db.add(XhsPublishPackage(tenant_id=1, blogger_id=10, skill_id=1, content_type="image_note",
                                 topic=f"t{i}", my_account_id=20, status="generated"))
    db.commit()
    pkg = db.query(XhsPublishPackage).first()
    mark_package_published(db, 1, pkg.id, True)

    out = build_overview(db, _settings(), tenant_id=1)
    assert out["creation"]["created"] == 3
    assert out["creation"]["published"] == 1
    # 省时 = 3*(40-10) = 90 分钟(无蒸馏)
    assert out["saved_minutes"] == 90
    assert out["library"]["my_account_count"] == 1


def test_account_dashboard_requires_mine_account(db):
    _seed_tenant(db)
    db.add(BloggerProfile(id=10, tenant_id=1, platform="xhs", account_type="benchmark", display_name="大V", homepage_url="h"))
    db.commit()
    with pytest.raises(ValueError):
        build_account_dashboard(db, _settings(), 1, 10)


def test_account_dashboard_viral_rate(db):
    _seed_tenant(db)
    db.add(BloggerProfile(id=20, tenant_id=1, platform="xhs", account_type="mine", display_name="我", homepage_url="h2"))
    db.flush()
    # 互动 10/10/10/100 → 均值 32.5,阈值 65,只有 100 是爆款
    for i, likes in enumerate([10, 10, 10, 100]):
        db.add(BloggerPost(tenant_id=1, blogger_id=20, platform="xhs", external_id=f"e{i}",
                           title="t", body_text="b", like_count=likes, status="active"))
    db.commit()
    out = build_account_dashboard(db, _settings(), 1, 20)
    assert out["content"]["post_count"] == 4
    assert out["content"]["viral_count"] == 1


def test_growth_snapshot_and_curve(db):
    _seed_tenant(db)
    account = BloggerProfile(id=20, tenant_id=1, platform="xhs", account_type="mine",
                             display_name="我", homepage_url="h2", follower_count=1000, note_total=5)
    db.add(account)
    db.commit()
    # 直接 upsert 两天快照(跳过 TikHub 刷新)
    db.add(AccountMetricSnapshot(tenant_id=1, account_id=20, captured_on=date(2026, 6, 1),
                                 follower_count=1000, note_total=5, total_interactions=0))
    db.add(AccountMetricSnapshot(tenant_id=1, account_id=20, captured_on=date(2026, 6, 2),
                                 follower_count=1100, note_total=6, total_interactions=0))
    db.commit()
    # 用 "all"(不设时间窗):固定种子日期不会随"今天"漂移出 30 天窗口(否则测试跨月边界会偶发失败)。
    out = build_account_growth(db, 1, 20, "all")
    assert len(out["points"]) == 2
    assert out["points"][0]["follower_count"] == 1000
    assert out["points"][-1]["follower_count"] == 1100
    assert "disclaimer" in out


def test_capture_snapshot_is_idempotent_per_day(db, monkeypatch):
    _seed_tenant(db)
    account = BloggerProfile(id=20, tenant_id=1, platform="xhs", account_type="mine",
                             display_name="我", homepage_url="h2", follower_count=500, note_total=3)
    db.add(account)
    db.commit()
    # stub 掉 TikHub 刷新,只测快照 upsert
    import app.blogger_distillation.service.collection as coll
    monkeypatch.setattr(coll, "refresh_blogger_profile", lambda *a, **k: account)
    today = date(2026, 6, 10)
    capture_account_snapshot(db, _settings(), account, today)
    account.follower_count = 600
    capture_account_snapshot(db, _settings(), account, today)
    snaps = db.query(AccountMetricSnapshot).filter_by(account_id=20, captured_on=today).all()
    assert len(snaps) == 1  # 同日不新增,覆盖
    assert snaps[0].follower_count == 600
