"""baseline schema — collapse the hand-rolled bootstrap into one revision

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-11

This baseline establishes PubSync's full current schema in a single revision by
delegating to the application's own bootstrap: ``Base.metadata.create_all`` over
the 21 ORM models plus ``ensure_runtime_schema`` (enum values, column default /
nullability adjustments, and seed rows for the default tenants/profiles/settings).

Because every table is defined as a SQLAlchemy model, future schema changes can be
generated normally with ``alembic revision --autogenerate -m "..."`` diffing against
``Base.metadata``.

For an existing database that already matches this schema, stamp it instead of
re-running:  ``alembic stamp 0001_baseline``.

Note: ``ensure_runtime_schema`` is intentionally still invoked on app startup as a
parallel fallback, so adopting Alembic is additive and does not break the existing
bootstrap. This baseline must be run in online mode (it opens a real connection);
``--sql`` offline generation is not supported for it.
"""

from __future__ import annotations

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reuse the proven application bootstrap so the Alembic-managed schema is
    # guaranteed identical to what the running app expects today.
    from app.database import create_db_and_tables

    create_db_and_tables()


def downgrade() -> None:
    from app.database import Base, engine

    Base.metadata.drop_all(bind=engine)
