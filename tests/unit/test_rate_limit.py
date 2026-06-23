"""Rate limiting smoke test against the real /api/auth/login endpoint.

Sends 6 bad-password attempts; the 6th must hit the slowapi
rate limiter (5/minute per IP) and return 429.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db import session as session_module
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import Role, User, UserRole  # noqa: F401


@pytest_asyncio.fixture
async def wired_app() -> AsyncIterator[tuple[AsyncClient, str]]:
    async_url = f"sqlite+aiosqlite:///{uuid.uuid4().hex}.db"

    bootstrap = create_async_engine(async_url, echo=False, future=True)
    async with bootstrap.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap.dispose()

    settings = get_settings()
    settings.database_url = async_url
    settings.jwt_secret = "test-rl"
    settings.jwt_issuer = "t"
    settings.jwt_audience = "t"
    settings.rabbitmq_url = "amqp://disabled:127.0.0.1:1/"

    await session_module.dispose_engine()
    engine = create_async_engine(async_url, echo=False, future=True, )
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session_module._engine = engine
    session_module._session_factory = factory

    async with factory() as s:
        role = Role(name="SELLER")
        s.add(role)
        await s.flush()
        user = User(
            username=f"u-{uuid.uuid4().hex[:6]}",
            email=f"u-{uuid.uuid4().hex[:6]}@example.com",
            password=hash_password("ValidPass1!"),
            name="Test",
            last_name="User",
        )
        s.add(user)
        await s.flush()
        s.add(UserRole(user_id=user.id, role_id=role.id))
        await s.commit()
        email = user.email

    from app.main import create_app

    app = create_app()

    @asynccontextmanager
    async def _noop(_):
        yield

    app.router.lifespan_context = _noop  # type: ignore[assignment]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, email

    await session_module.dispose_engine()
    await engine.dispose()


@pytest.mark.asyncio
async def test_login_rate_limit(wired_app) -> None:
    client, email = wired_app
    statuses = [
        (await client.post(
            "/api/auth/login",
            json={"email": email, "password": "wrong"},
        )).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
