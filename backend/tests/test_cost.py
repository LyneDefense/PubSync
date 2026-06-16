import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.cost import context, pricing
from app.database import Base
from app.models import CostEvent, SystemConfig


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    # 让 cost.context 用内存库(它内部用 SessionLocal 开会话)。
    monkeypatch.setattr(context, "SessionLocal", factory)
    return factory


# —— pricing ——
def test_price_text_and_image():
    p = pricing.default_prices()
    assert pricing.price_text(p, "gpt-4.1", 1000, 1000) == pytest.approx(0.01)
    assert pricing.price_image(p, "gpt-image-1", 1) == pytest.approx(0.04)
    # 未知模型走兜底单价
    assert pricing.price_text(p, "unknown-model", 1000, 0) == pytest.approx(0.001)


def test_load_prices_merges_override(session_factory):
    db = session_factory()
    db.add(SystemConfig(key=pricing.CONFIG_KEY, value=json.dumps({"text": {"gpt-4.1": {"input_per_1k": 1, "output_per_1k": 2}}})))
    db.commit()
    merged = pricing.load_prices(db)
    assert merged["text"]["gpt-4.1"] == {"input_per_1k": 1, "output_per_1k": 2}
    assert "image-01" in merged["image"]  # 内置项仍在
    db.close()


# —— context ——
def test_capture_buffers_then_flushes(session_factory):
    with context.cost_capture(tenant_id=1, task_id="task-1"):
        context.record_tikhub("collection", requests=5, cost_usd=0.05)
        context.add_cost(provider="openai", kind="text", cost_usd=0.01, quantity=100, unit="token")
    db = session_factory()
    rows = list(db.scalars(select(CostEvent)))
    assert len(rows) == 2
    assert all(r.tenant_id == 1 and r.task_id == "task-1" for r in rows)
    assert {r.provider for r in rows} == {"tikhub", "openai"}
    db.close()


def test_add_cost_without_context_writes_directly(session_factory):
    context.add_cost(provider="minimax", kind="text", cost_usd=0.02, quantity=200, unit="token")
    db = session_factory()
    rows = list(db.scalars(select(CostEvent)))
    assert len(rows) == 1 and rows[0].tenant_id is None and rows[0].task_id is None
    db.close()


def test_record_text_usage_computes_cost(session_factory):
    with context.cost_capture(tenant_id=2, task_id="task-2"):
        context.record_text_usage("minimax", "MiniMax-M2.7", {"usage": {"prompt_tokens": 1000, "completion_tokens": 1000}})
    db = session_factory()
    row = db.scalars(select(CostEvent)).one()
    assert row.provider == "minimax" and row.unit == "token" and row.quantity == 2000
    assert row.cost_usd == pytest.approx(0.002)  # 1k*0.001 + 1k*0.001
    assert json.loads(row.meta_json)["prompt_tokens"] == 1000
    db.close()
