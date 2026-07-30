"""Alembic environment.

The database URL comes from Jarvis's own settings rather than alembic.ini, so
there is exactly one place a deployment is configured.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from jarvis.config import get_settings
from jarvis.persistence.db import normalise_url
from jarvis.persistence.models import Base
from jarvis.trading.database import models as _trading_models  # noqa: F401  registers tables on Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit(
            "JARVIS_DATABASE_URL is not set — nothing to migrate. "
            "Local-first installs on SQLite create their schema on start."
        )
    return normalise_url(settings.database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# Vector indexes are created by raw DDL because SQLAlchemy has no HNSW
# construct. Autogenerate cannot see them in the metadata and would helpfully
# emit a DROP for each one on the next migration, so they are excluded from
# comparison entirely.
UNMANAGED_INDEXES = {"ix_memories_embedding_hnsw", "ix_document_chunks_embedding_hnsw"}


def _managed_by_alembic(obj: object, name: str | None, type_: str, *args: object) -> bool:
    return not (type_ == "index" and name in UNMANAGED_INDEXES)


def do_run_migrations(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        # The vector type must exist before any table that uses it.
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_managed_by_alembic,
        # SQLite cannot ALTER most things in place; batch mode rewrites the
        # table instead, so one migration script works on both dialects.
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()

    connectable = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        # SQLAlchemy 2 is commit-as-you-go: without this the whole migration is
        # rolled back when the connection closes, and it fails *silently* —
        # alembic reports success and the database is untouched.
        await connection.commit()
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
