import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.blogger_distillation.service.extract import extract_note_key, upsert_post
from app.database import Base
from app.models import BloggerPost, BloggerProfile, Tenant


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add(Tenant(id=1, name="T", slug="t"))
        session.add(BloggerProfile(id=1, tenant_id=1, platform="xhs", account_type="benchmark", display_name="大V", homepage_url="h"))
        session.commit()
        yield session
    finally:
        session.close()


def test_extract_note_key_prefers_biz_id():
    raw = {"note_id": "62e64e99000000002302b72b", "biz_id": "280039352108496683"}
    assert extract_note_key(raw, raw, "fallback") == "280039352108496683"


def test_extract_note_key_falls_back_to_note_id():
    raw = {"note_id": "abc", "title": "x"}
    assert extract_note_key(raw, raw, "abc") == "abc"


def test_extract_note_key_uses_card_id_when_biz_empty():
    # 真实 bug:biz_id 为空、顶层/列表 note_id 漂移,但笔记卡自身 id 稳定 → 用卡 id 当 note_key 去重。
    raw = {"id": "68d95a40000000001003f999", "note_id": "68d95a400000000210037ca3", "bizId": ""}
    # fallback(漂移的 external_id)不该被采用,应取稳定的卡 id。
    assert extract_note_key(raw, raw, "68d95a400000000210037ca3") == "68d95a40000000001003f999"


def _data(external_id: str, note_key: str, title: str):
    return {
        "external_id": external_id,
        "note_key": note_key,
        "url": "",
        "title": title,
        "body_text": "正文",
        "content_type": "video",
        "content_subtype": "talking_video",
        "hashtags_json": "[]",
        "cover_url": "",
        "media_urls_json": "[]",
        "transcript_text": "x" * 300,
        "asr_status": "succeeded",
        "asr_error": "",
        "published_at": None,
        "like_count": 1,
        "favorite_count": 1,
        "comment_count": 1,
        "share_count": 0,
        "score": 1.0,
        "comments_json": "[]",
        "raw_json": "{}",
    }


def test_upsert_dedupes_by_note_key_across_drifting_note_id(db):
    blogger = db.get(BloggerProfile, 1)
    # 同一篇笔记,两次采集 note_id 漂移,但 biz_id(note_key)相同 → 应覆盖为同一行,不重复。
    p1 = upsert_post(db, 1, blogger, _data("62e64e99000000002302b72b", "280039352108496683", "停止内耗 v1"))
    db.commit()
    p2 = upsert_post(db, 1, blogger, _data("62e64e990000000223023211", "280039352108496683", "停止内耗 v2"))
    db.commit()
    assert p1.id == p2.id  # 同一行
    assert db.query(BloggerPost).count() == 1
    assert p2.title == "停止内耗 v2"  # 覆盖为最新
    assert p2.external_id == "62e64e990000000223023211"  # external_id 更新到最新 note_id


def test_upsert_falls_back_to_external_id_when_no_note_key(db):
    blogger = db.get(BloggerProfile, 1)
    d = _data("note-1", "", "无 biz_id")
    a = upsert_post(db, 1, blogger, d)
    db.commit()
    b = upsert_post(db, 1, blogger, _data("note-1", "", "无 biz_id 覆盖"))
    db.commit()
    assert a.id == b.id
    assert db.query(BloggerPost).count() == 1
