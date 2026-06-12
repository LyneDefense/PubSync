from collections.abc import Generator

from sqlalchemy import create_engine
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


# Re-exported for backward compatibility. The large schema bootstrap (table
# creation, runtime migrations and seed data) lives in app.db.bootstrap to keep
# this module focused on the engine/session/Base. Imported at the bottom so that
# Base and engine are already defined when bootstrap imports them back.
from app.db.bootstrap import create_db_and_tables, ensure_runtime_schema  # noqa: E402

__all__ = ["Base", "engine", "SessionLocal", "get_db", "create_db_and_tables", "ensure_runtime_schema"]
