import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - 注册所有表
from app.blogger_distillation.service.asr_step import _reuse_existing_transcript
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


def _seed(db, *, note_key: str, asr_status: str, transcript: str):
    db.add(
        BloggerPost(
            tenant_id=1,
            blogger_id=1,
            platform="xhs",
            external_id="old-note-id",
            note_key=note_key,
            title="t",
            content_type="video",
            asr_status=asr_status,
            transcript_text=transcript,
        )
    )
    db.commit()


def test_reuse_hits_succeeded_transcript(db):
    # 同篇笔记 note_id 漂移被当成新笔记重抓 → 命中已转写记录,复用,跳过 ASR。
    _seed(db, note_key="biz-1", asr_status="succeeded", transcript="逐字稿内容")
    blogger = db.get(BloggerProfile, 1)
    normalized = {"note_key": "biz-1", "transcript_text": "", "asr_status": "pending"}
    assert _reuse_existing_transcript(db, 1, blogger, normalized) is True
    assert normalized["transcript_text"] == "逐字稿内容"
    assert normalized["asr_status"] == "succeeded"


def test_reuse_hits_subtitle_transcript(db):
    _seed(db, note_key="biz-2", asr_status="subtitle", transcript="中文字幕稿")
    blogger = db.get(BloggerProfile, 1)
    normalized = {"note_key": "biz-2", "transcript_text": "", "asr_status": "pending"}
    assert _reuse_existing_transcript(db, 1, blogger, normalized) is True
    assert normalized["asr_status"] == "subtitle"


def test_no_reuse_when_existing_failed(db):
    # 补转写场景:已有记录是 failed/skipped(正是要补的),不能复用,必须真跑 ASR。
    _seed(db, note_key="biz-3", asr_status="failed", transcript="")
    blogger = db.get(BloggerProfile, 1)
    normalized = {"note_key": "biz-3", "transcript_text": "", "asr_status": "pending"}
    assert _reuse_existing_transcript(db, 1, blogger, normalized) is False
    assert normalized["transcript_text"] == ""


def test_no_reuse_when_no_match(db):
    _seed(db, note_key="biz-4", asr_status="succeeded", transcript="x")
    blogger = db.get(BloggerProfile, 1)
    normalized = {"note_key": "biz-other", "transcript_text": "", "asr_status": "pending"}
    assert _reuse_existing_transcript(db, 1, blogger, normalized) is False


def test_no_reuse_when_blank_note_key(db):
    _seed(db, note_key="", asr_status="succeeded", transcript="x")
    blogger = db.get(BloggerProfile, 1)
    normalized = {"note_key": "", "transcript_text": "", "asr_status": "pending"}
    assert _reuse_existing_transcript(db, 1, blogger, normalized) is False
