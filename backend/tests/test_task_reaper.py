from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.database import Base
from app.models import OperationTask, OperationTaskEvent, TaskStatus, Tenant
from app.services.task_service import reap_stale_tasks_in_session

NOW = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Tenant(id=1, name="T", slug="t"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _task(db, tid: str, status: TaskStatus, age_minutes: int) -> OperationTask:
    ts = NOW - timedelta(minutes=age_minutes)
    t = OperationTask(id=tid, tenant_id=1, task_type="blogger_collection", status=status,
                      message="running", created_at=ts, updated_at=ts)
    db.add(t)
    db.commit()
    return t


def _event(db, task_id: str, age_minutes: int) -> None:
    db.add(OperationTaskEvent(tenant_id=1, task_id=task_id, step_name="笔记详情", status="running",
                              message="采集", created_at=NOW - timedelta(minutes=age_minutes)))
    db.commit()


def test_reaps_running_task_with_no_recent_events(db):
    _task(db, "stale", TaskStatus.running, age_minutes=60)
    _event(db, "stale", age_minutes=40)  # 最近一条事件 40 分钟前 > 20 分钟阈值
    reaped = reap_stale_tasks_in_session(db, NOW, stale_minutes=20)
    assert reaped == ["stale"]
    t = db.get(OperationTask, "stale")
    assert t.status == TaskStatus.failed
    assert "标记为失败" in (t.error_message or "")
    # 同时写了一条失败事件,前端时间线能看到
    ev = db.query(OperationTaskEvent).filter_by(task_id="stale", status="failed").all()
    assert len(ev) == 1


def test_does_not_reap_fresh_running_task(db):
    _task(db, "fresh", TaskStatus.running, age_minutes=60)
    _event(db, "fresh", age_minutes=2)  # 2 分钟前还有进展
    reaped = reap_stale_tasks_in_session(db, NOW, stale_minutes=20)
    assert reaped == []
    assert db.get(OperationTask, "fresh").status == TaskStatus.running


def test_uses_updated_at_when_no_events(db):
    _task(db, "noevt", TaskStatus.running, age_minutes=30)  # 无事件,30 分钟前创建/更新
    reaped = reap_stale_tasks_in_session(db, NOW, stale_minutes=20)
    assert reaped == ["noevt"]


def test_ignores_queued_and_terminal_tasks(db):
    _task(db, "queued", TaskStatus.queued, age_minutes=120)
    _task(db, "done", TaskStatus.succeeded, age_minutes=120)
    _task(db, "failed", TaskStatus.failed, age_minutes=120)
    reaped = reap_stale_tasks_in_session(db, NOW, stale_minutes=20)
    assert reaped == []
    assert db.get(OperationTask, "queued").status == TaskStatus.queued


def test_reaps_cancel_requested_too(db):
    _task(db, "cancelreq", TaskStatus.cancel_requested, age_minutes=40)
    reaped = reap_stale_tasks_in_session(db, NOW, stale_minutes=20)
    assert reaped == ["cancelreq"]
