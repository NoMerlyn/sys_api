"""Tests for the AuditLog repository and the `audit()` context helper."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.application.audit import audit
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.audit_log import AuditLog
from app.infrastructure.repositories.audit_log_repository import (
    SqlAuditLogRepository,
)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """Per-test in-memory SQLite session with all tables created."""
    url = f"sqlite+aiosqlite:///{uuid.uuid4().hex}.db"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    yield Session()
    await engine.dispose()


@pytest.mark.asyncio
async def test_add_writes_a_row(session: AsyncSession) -> None:
    repo = SqlAuditLogRepository(session)
    await repo.add(
        action="LOGIN_SUCCESS",
        entity="USER",
        user_id=7,
        detail="alice@example.com",
        ip_address="127.0.0.1",
    )
    await session.commit()
    rows = (await session.execute(_select_all())).scalars().all()
    assert len(rows) == 1
    r = rows[0]
    assert r.action == "LOGIN_SUCCESS"
    assert r.entity == "USER"
    assert r.user_id == 7
    assert r.detail == "alice@example.com"
    assert r.ip_address == "127.0.0.1"
    assert r.created_at is not None


@pytest.mark.asyncio
async def test_audit_context_helper_writes_a_row(session: AsyncSession) -> None:
    async with audit(session) as log:
        await log.add(
            action="CREATE",
            entity="INVOICE",
            entity_id=42,
            user_id=3,
        )
    await session.commit()
    rows = (await session.execute(_select_all())).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "CREATE"
    assert rows[0].entity == "INVOICE"
    assert rows[0].entity_id == 42


@pytest.mark.asyncio
async def test_list_filters_by_action(session: AsyncSession) -> None:
    repo = SqlAuditLogRepository(session)
    for i in range(3):
        await repo.add(action="LOGIN_SUCCESS", entity="USER", user_id=i)
    await repo.add(action="LOGIN_FAILED", entity="USER", user_id=99)
    await session.commit()

    rows, total = await repo.list(page=1, limit=10, action="LOGIN_SUCCESS")
    assert total == 3
    assert {r["user_id"] for r in rows} == {0, 1, 2}

    rows, total = await repo.list(page=1, limit=10, action="LOGIN_FAILED")
    assert total == 1
    assert rows[0]["user_id"] == 99


@pytest.mark.asyncio
async def test_list_paginates(session: AsyncSession) -> None:
    repo = SqlAuditLogRepository(session)
    for i in range(7):
        await repo.add(action="X", entity="Y", entity_id=i)
    await session.commit()
    rows, total = await repo.list(page=1, limit=3)
    assert total == 7
    assert len(rows) == 3
    rows, total = await repo.list(page=3, limit=3)
    assert total == 7
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_orders_by_id_desc(session: AsyncSession) -> None:
    repo = SqlAuditLogRepository(session)
    for i in range(5):
        await repo.add(action="A", entity="E", entity_id=i)
    await session.commit()
    rows, _ = await repo.list(page=1, limit=10)
    ids = [r["entity_id"] for r in rows]
    assert ids == [4, 3, 2, 1, 0]


def _select_all():
    from sqlalchemy import select

    return select(AuditLog)