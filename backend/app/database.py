from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_and_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()


def ensure_runtime_schema() -> None:
    statements = [
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(200)",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS dedup_status VARCHAR(30) NOT NULL DEFAULT 'unique'",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS duplicate_of_id INTEGER REFERENCES news_items(id)",
        "ALTER TABLE news_items ADD COLUMN IF NOT EXISTS dedup_reason TEXT",
        "CREATE INDEX IF NOT EXISTS ix_news_items_dedup_status ON news_items(dedup_status)",
        "CREATE INDEX IF NOT EXISTS ix_news_items_duplicate_of_id ON news_items(duplicate_of_id)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
