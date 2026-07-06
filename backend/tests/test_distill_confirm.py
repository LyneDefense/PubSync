"""蒸馏转正(confirm)不变量:归档旧 active 画像 → pending 转正 → run 变 succeeded。

这是「一键建档 / 重蒸即覆盖 / 去多画像」的核心保证 —— 建档⑤ 和「更新画像」蒸完
自动调 confirm_blogger_distillation,产物直接成为当前画像,用户无需手动确认。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.blogger_distillation.service import confirm_blogger_distillation
from app.database import Base
from app.models import BloggerDistillationRun, BloggerProfile, BloggerSkill, Tenant


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _run(db, *, status):
    run = BloggerDistillationRun(tenant_id=1, blogger_id=1, status=status)
    db.add(run)
    db.flush()
    return run


def _skill(db, *, run_id, status):
    skill = BloggerSkill(
        tenant_id=1, blogger_id=1, run_id=run_id, name="创作画像", skill_markdown="# 画像", status=status
    )
    db.add(skill)
    db.flush()
    return skill


def _seed(db):
    db.add(Tenant(id=1, name="T", slug="t"))
    db.add(BloggerProfile(id=1, tenant_id=1, platform="xhs", account_type="benchmark", display_name="小小", homepage_url="h"))
    db.flush()


def test_confirm_promotes_pending_and_archives_old_active(db):
    _seed(db)
    old_run = _run(db, status="succeeded")
    old_skill = _skill(db, run_id=old_run.id, status="active")  # 旧画像(已转正过)
    new_run = _run(db, status="pending_confirmation")
    new_skill = _skill(db, run_id=new_run.id, status="pending_confirmation")  # 本次重蒸的待确认画像
    db.commit()

    result = confirm_blogger_distillation(db, 1, new_run.id)

    assert result.run.id == new_run.id
    db.refresh(old_skill)
    db.refresh(new_skill)
    db.refresh(new_run)
    assert old_skill.status == "archived"  # 去多画像:旧 active 让位
    assert new_skill.status == "active"  # 新画像转正 → 档案页 _portraits 才看得到
    assert new_run.status == "succeeded"
    blogger = db.get(BloggerProfile, 1)
    assert blogger.last_distilled_at is not None


def test_confirm_first_portrait_no_prior_active(db):
    """新博主(此前无 active 画像)—— 建档⑤自动蒸馏 + 转正后应直接出画像,这正是「小小」的场景。"""
    _seed(db)
    run = _run(db, status="pending_confirmation")
    skill = _skill(db, run_id=run.id, status="pending_confirmation")
    db.commit()

    confirm_blogger_distillation(db, 1, run.id)

    db.refresh(skill)
    assert skill.status == "active"
    actives = db.query(BloggerSkill).filter_by(blogger_id=1, status="active").count()
    assert actives == 1  # 有且仅有一份当前画像


def test_confirm_rejects_non_pending_run(db):
    _seed(db)
    run = _run(db, status="succeeded")
    db.commit()
    with pytest.raises(ValueError):
        confirm_blogger_distillation(db, 1, run.id)  # 只能确认 pending_confirmation
