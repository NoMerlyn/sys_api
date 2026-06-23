"""Unit of Work context.

This is intentionally thin: SQLAlchemy's `session_scope()` is already a
UoW (it opens a transaction, commits on success, rolls back on exception).
This module re-exports it so handlers can `from app.application.common.uow
import uow` and stay decoupled from `app.infrastructure.db.session`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import session_scope  # re-export


@asynccontextmanager
async def uow() -> AsyncIterator[AsyncSession]:
    """Open an async UoW scoped session. Use as `async with uow() as s:`."""
    async with session_scope() as session:
        yield session
