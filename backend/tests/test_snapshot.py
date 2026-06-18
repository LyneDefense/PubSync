import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.blogger_distillation.service.crud import (
    create_snapshot,
    delete_snapshot,
    list_snapshots,
    update_snapshot,
)
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


def _seed(db, n=5):
    db.add(Tenant(id=1, name="T", slug="t"))
    db.add(BloggerProfile(id=1, tenant_id=1, platform="xhs", account_type="benchmark", display_name="大V", homepage_url="h"))
    ids = []
    for i in range(n):
        post = BloggerPost(
            tenant_id=1, blogger_id=1, platform="xhs", external_id=f"e{i}",
            title=f"标题{i}", body_text=f"正文{i}", like_count=100 - i,
        )
        db.add(post)
        db.flush()
        ids.append(post.id)
    db.commit()
    return ids


def test_create_and_list_snapshot(db):
    ids = _seed(db)
    snap = create_snapshot(db, 1, 1, "我的选材", ids[:3])
    assert snap.id is not None
    assert snap.post_ids == ids[:3]
    assert snap.post_count == 3
    listed = list_snapshots(db, 1, 1)
    assert [s.id for s in listed] == [snap.id]


def test_create_snapshot_rejects_empty(db):
    _seed(db)
    with pytest.raises(ValueError):
        create_snapshot(db, 1, 1, "空", [])


def test_create_snapshot_rejects_foreign_blogger(db):
    ids = _seed(db)
    with pytest.raises(ValueError):
        create_snapshot(db, 1, 999, "不存在的博主", ids[:2])


def test_update_snapshot_rename(db):
    ids = _seed(db)
    snap = create_snapshot(db, 1, 1, "旧名", ids[:2])
    renamed = update_snapshot(db, 1, snap.id, name="新名")
    assert renamed.name == "新名"
    with pytest.raises(ValueError):
        update_snapshot(db, 1, snap.id, name="   ")


def test_update_snapshot_repick(db):
    ids = _seed(db)
    snap = create_snapshot(db, 1, 1, "选材", ids[:2])
    updated = update_snapshot(db, 1, snap.id, post_ids=ids[:4])
    assert updated.post_ids == ids[:4]
    assert updated.name == "选材"  # 只传 post_ids 不动名字
    with pytest.raises(ValueError):
        update_snapshot(db, 1, snap.id, post_ids=[])


def test_delete_snapshot(db):
    ids = _seed(db)
    snap = create_snapshot(db, 1, 1, "待删", ids[:2])
    delete_snapshot(db, 1, snap.id)
    assert list_snapshots(db, 1, 1) == []
    with pytest.raises(ValueError):
        delete_snapshot(db, 1, snap.id)


def test_tenant_isolation(db):
    ids = _seed(db)
    snap = create_snapshot(db, 1, 1, "T1", ids[:2])
    # 别的租户看不到 / 改不了
    assert list_snapshots(db, 2, 1) == []
    with pytest.raises(ValueError):
        update_snapshot(db, 2, snap.id, name="x")
    with pytest.raises(ValueError):
        delete_snapshot(db, 2, snap.id)
