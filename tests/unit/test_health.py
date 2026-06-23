"""Health check endpoint tests.

Verifies:
- GET /health/live always returns 200.
- GET /health/ready returns 200 when DB is reachable.
- /health/* is unauthenticated.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.infrastructure.db import session as session_module
from app.infrastructure.db.base import Base


@pytest_asyncio.fixture
async def app_with_db() -> AsyncIterator[AsyncClient]:
    async_url = f"sqlite+aiosqlite:///{uuid.uuid4().hex}.db"

    bootstrap = create_async_engine(async_url, echo=False, future=True)
    async with bootstrap.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap.dispose()

    settings = get_settings()
    settings.database_url = async_url
    settings.jwt_secret = "test"
    settings.jwt_issuer = "t"
    settings.jwt_audience = "t"
    settings.rabbitmq_url = "amqp://disabled:127.0.0.1:1/"

    await session_module.dispose_engine()
    engine = create_async_engine(async_url, echo=False, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session_module._engine = engine
    session_module._session_factory = factory

    from app.main import create_app

    app = create_app()

    @asynccontextmanager
    async def _noop(_):
        yield

    app.router.lifespan_context = _noop  # type: ignore[assignment]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await session_module.dispose_engine()
    await engine.dispose()
    import os

    with contextlib.suppress(FileNotFoundError):
        os.remove(async_url.split("/")[-1])


@pytest.mark.asyncio
async def test_live_returns_200_without_auth(app_with_db: AsyncClient) -> None:
    r = await app_with_db.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_returns_200_when_db_ok(app_with_db: AsyncClient) -> None:
    r = await app_with_db.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
