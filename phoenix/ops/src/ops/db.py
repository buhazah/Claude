"""Database setup.

SQLite, synchronous, `create_all` at startup. No migrations, no async, no
connection pool tuning — this is an internal tool for two people running ten
clients, and every one of those would be sophistication we would then have to
maintain. When it stops being enough, the deficiency register will say so.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ops.models import Base

DEFAULT_PATH = Path(os.environ.get("PHOENIX_OPS_DB", "phoenix-ops.db"))

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def configure(url: str | None = None) -> Engine:
    """Build the engine and create tables. Safe to call repeatedly."""
    global _engine, _Session
    url = url or os.environ.get("PHOENIX_OPS_URL") or f"sqlite:///{DEFAULT_PATH}"
    kwargs: dict[str, object] = {}
    if url == "sqlite://":
        # An in-memory database lives inside its connection, so the default
        # pool hands every caller a different, empty database. Tests need one.
        kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    _engine = create_engine(url, future=True, **kwargs)  # type: ignore[arg-type]
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def engine() -> Engine:
    return _engine or configure()


@contextmanager
def session() -> Iterator[Session]:
    """A unit of work. Commits on clean exit, rolls back on anything else."""
    if _Session is None:
        configure()
    assert _Session is not None
    db = _Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset() -> None:
    """Drop everything. Tests only."""
    Base.metadata.drop_all(engine())
    Base.metadata.create_all(engine())
