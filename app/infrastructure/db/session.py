"""Async SQLAlchemy engine and session helpers.

The engine is created once per process. `session_scope()` is a context
manager that opens an async session inside a transaction; commits on
clean exit, rolls back on exception, always closes.

Repositories receive a `Session` and never create their own — this is the
Unit of Work boundary.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.db.base import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> AsyncEngine:
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    if database_url.startswith("postgresql+asyncpg"):
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _session_factory = async_sessionmaker(
            bind=_engine,
            expire_on_commit=False,
            autoflush=False,
        )
    elif database_url.startswith("postgresql"):
        # Sync engine for scripts (seed, alembic env, etc.) that don't need async.
        from sqlalchemy import create_engine as _create_sync
        from sqlalchemy.orm import sessionmaker as _sessionmaker_sync

        _engine = _create_sync(
            database_url.replace("postgresql://", "postgresql+psycopg2://"),
            echo=False,
            pool_pre_ping=True,
        )
        _session_factory = _sessionmaker_sync(  # type: ignore[assignment]
            bind=_engine,
            expire_on_commit=False,
            autoflush=False,
        )
    else:
        raise ValueError(f"Unsupported database URL: {database_url!r}")
    return _engine


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialised. Call init_engine() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory not initialised. Call init_engine() first.")
    return _session_factory


def _is_async_factory(factory) -> bool:
    """A factory is async if calling it returns an object with __aenter__.

    We can't ask the factory itself because `async_sessionmaker` is callable
    but not itself an async context manager.
    """
    try:
        probe = factory()
    except Exception:
        return False
    try:
        return hasattr(probe, "__aenter__")
    finally:
        close = getattr(probe, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open an ASYNC session inside a transaction. Use as `async with session_scope() as s:`."""
    factory = get_session_factory()
    if not _is_async_factory(factory):
        raise RuntimeError(
            "session_scope() requires an async session factory. "
            "Did you init the engine with a sync URL? Use sync_session_scope() instead."
        )
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def sync_session_scope():
    """Return a sync context manager for the active (sync) session factory."""
    factory = get_session_factory()
    if _is_async_factory(factory):
        raise RuntimeError(
            "sync_session_scope() requires a sync session factory. "
            "Did you init the engine with an async URL? Use session_scope() instead."
        )

    @contextmanager
    def _scope():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    return _scope()


__all__ = [
    "Base",
    "init_engine",
    "dispose_engine",
    "get_engine",
    "get_session_factory",
    "session_scope",
    "sync_session_scope",
]
