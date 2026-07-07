"""选题重构 P2:选题 = 对标方法 × 我的账号受众 [× 意图]。

锁两条不变量:
1. 我的账号有受众数据 → 渲染进 prompt(读者最常问 + 高频关注点)。
2. 缺账号 / 越权 / 无受众数据 → 降级不挡路(返回 None / 明确降级文案,禁止编造需求)。
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.database import Base
from app.models import BloggerProfile, Tenant
from app.xhs_creation.service import _my_account_audience, _render_audience_for_topic


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _mine(db, *, blogger_id, tenant_id, attribution_json=""):
    db.add(
        BloggerProfile(
            id=blogger_id,
            tenant_id=tenant_id,
            platform="xhs",
            account_type="mine",
            display_name="我的账号",
            homepage_url="h",
            attribution_json=attribution_json,
        )
    )
    db.flush()


_AUDIENCE = {
    "questions": [{"theme": "猫粮配料表怎么看", "sample": "配料表第一位是肉才行吗"}],
    "focus_points": ["价格", "避坑"],
    "note": "依据 40 条评论",
}


def test_render_degrades_without_audience():
    text = _render_audience_for_topic(None)
    assert "暂无" in text and "不要凭空编造" in text


def test_render_includes_questions_and_focus():
    text = _render_audience_for_topic(_AUDIENCE)
    assert "猫粮配料表怎么看" in text
    assert "价格" in text and "避坑" in text


def test_my_account_audience_none_id_returns_none(db):
    assert _my_account_audience(db, tenant_id=1, my_blogger_id=None) is None


def test_my_account_audience_cross_tenant_blocked(db):
    _mine(db, blogger_id=5, tenant_id=2, attribution_json=json.dumps(_AUDIENCE, ensure_ascii=False))
    # 越权:租户 1 拿不到租户 2 的账号 → None(降级不挡路)
    assert _my_account_audience(db, tenant_id=1, my_blogger_id=5) is None


def test_my_account_audience_happy_path(db):
    db.add(Tenant(id=1, name="T", slug="t"))
    _mine(db, blogger_id=5, tenant_id=1, attribution_json=json.dumps(_AUDIENCE, ensure_ascii=False))
    got = _my_account_audience(db, tenant_id=1, my_blogger_id=5)
    assert got is not None and got["questions"][0]["theme"] == "猫粮配料表怎么看"


def test_my_account_audience_empty_attribution_returns_none(db):
    db.add(Tenant(id=1, name="T", slug="t"))
    _mine(db, blogger_id=6, tenant_id=1, attribution_json="")  # 没跑过受众需求
    assert _my_account_audience(db, tenant_id=1, my_blogger_id=6) is None
