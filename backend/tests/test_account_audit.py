import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.account_audit.agent.context import AuditContext
from app.account_audit.agent.guide import build_audit_prompt
from app.account_audit.agent.sensors import AuditSchemaSensor, evaluate_audit_quality
from app.account_audit.service import build_account_content
from app.database import Base
from app.models import BloggerPost, BloggerProfile, Tenant


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed(db):
    db.add(Tenant(id=1, name="T", slug="t"))
    db.add(BloggerProfile(id=1, tenant_id=1, platform="xhs", account_type="mine", display_name="我", homepage_url="h"))
    for i in range(3):
        db.add(
            BloggerPost(
                tenant_id=1, blogger_id=1, platform="xhs", external_id=f"e{i}",
                title=f"标题{i}", body_text=f"正文{i}", like_count=10, favorite_count=5, comment_count=2,
            )
        )
    db.commit()


def test_build_account_content(db):
    _seed(db)
    text = build_account_content(db, 1, 1, [])
    assert "共 3 篇" in text and "平均赞 10" in text
    assert "标题0" in text and "正文0" in text


def test_build_account_content_empty(db):
    text = build_account_content(db, 1, 999, [])
    assert text == ""


def test_prompt_branches_by_kind():
    bm = build_audit_prompt(AuditContext("xhs", "小红书", "benchmark", "我", "我的内容", "大V", "对标内容"))
    assert "对标账号" in bm and "对标内容" in bm
    self = build_audit_prompt(AuditContext("xhs", "小红书", "self", "我", "我的内容"))
    assert "诊断" in self and "对标账号" not in self


def test_self_schema_sensor_requires_strengths_or_gaps():
    ctx = AuditContext("xhs", "小红书", "self", "我", "我的内容")
    bad = AuditSchemaSensor().check({"dimensions": [], "conclusion": "x" * 30}, ctx)
    assert not bad.passed
    good = AuditSchemaSensor().check({"strengths": ["a"], "conclusion": "x" * 30}, ctx)
    assert good.passed


def test_quality_scoring_kind_aware():
    self_full = {"strengths": ["a"], "gaps": ["b"], "actions": ["c", "d"], "conclusion": "x" * 30}
    assert evaluate_audit_quality(self_full, kind="self")["score"] == 100
    bench_full = {
        "dimensions": [{"name": str(i), "benchmark": "b", "mine": "m", "gap": "g"} for i in range(5)],
        "strengths": ["a"], "gaps": ["b"], "actions": ["c", "d"], "conclusion": "x" * 30,
    }
    assert evaluate_audit_quality(bench_full, kind="benchmark")["score"] == 100
