"""Alembic environment.

The migration target metadata is the application's ORM ``Base.metadata`` and the
database URL is pulled from the app settings, so ``alembic revision --autogenerate``
diffs against the real models and runs against the configured database.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Importing the models registers every table on Base.metadata.
import app.models  # noqa: F401
from app.config import get_settings
from app.database import Base


config = context.config
# disable_existing_loggers=False：以编程方式从应用内运行迁移时（run_migrations），
# 不要清掉应用已配置好的日志器（configure_logging）。
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_settings().database_url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
