"""Database lifecycle.

Two supported shapes, one code path:

- **SQLite/aiosqlite** — the local-first default. No server, no extension, and
  the file lives on the user's own machine.
- **Postgres/asyncpg + pgvector** — the server deployment, where recall is
  backed by a real ANN index.

Dialect differences stop at this module and ``EmbeddingVector``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from jarvis.kernel.errors import ConfigurationError
from jarvis.persistence.models import Base

log = structlog.get_logger(__name__)


def normalise_url(url: str) -> str:
    """Accept the URLs people actually type and make them async drivers."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


class Database:
    """Owns the engine and session factory."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = normalise_url(url)
        self.dialect = "postgresql" if "postgresql" in self.url else "sqlite"
        try:
            self._engine: AsyncEngine = create_async_engine(
                self.url,
                echo=echo,
                # SQLite has no server-side pool to manage; Postgres gets a
                # pre-ping so a recycled connection fails here, not mid-request.
                pool_pre_ping=self.dialect == "postgresql",
            )
        except Exception as exc:
            raise ConfigurationError(f"cannot open database {url!r}: {exc}") from exc
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def is_postgres(self) -> bool:
        return self.dialect == "postgresql"

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._sessions() as session:
            yield session

    async def create_all(self) -> None:
        """Create the schema directly.

        Used for SQLite and for tests. Server deployments run Alembic instead,
        so migrations stay the single source of truth for Postgres.
        """
        async with self._engine.begin() as connection:
            if self.is_postgres:
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)

    async def healthy(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            log.warning("database_unhealthy", error=str(exc))
            return False

    async def dispose(self) -> None:
        await self._engine.dispose()
