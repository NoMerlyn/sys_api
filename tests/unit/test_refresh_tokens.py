"""Refresh token handler tests (using an in-memory SQLite + uow)."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.auth import (
    IssueRefreshTokenHandler,
    LogoutAllHandler,
    LogoutHandler,
    RefreshAccessTokenHandler,
)
from app.application.common.interfaces.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.application.common.interfaces.user_repository import IUserRepository
from app.config import get_settings
from app.core.security import hash_password
from app.infrastructure.db import session as session_module
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (  # noqa: F401
    RefreshToken,
    Role,
    User,
    UserRole,
)


@pytest_asyncio.fixture
async def wired() -> AsyncIterator[tuple[RefreshTokenRepository, IUserRepository, int]]:
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

    from app.infrastructure.repositories.refresh_token_repository import (
        SqlRefreshTokenRepository,
    )
    from app.infrastructure.repositories.user_repository import SqlUserRepository

    async with factory() as s:
        role = Role(name="SELLER")
        s.add(role)
        await s.flush()
        user = User(
            username="u1",
            email="u1@example.com",
            password=hash_password("ValidPass1!"),
            name="S",
            last_name="O",
        )
        s.add(user)
        await s.flush()
        s.add(UserRole(user_id=user.id, role_id=role.id))
        await s.commit()
        user_id = user.id

    yield (
        SqlRefreshTokenRepository.__new__(SqlRefreshTokenRepository),
        SqlUserRepository.__new__(SqlUserRepository),
        user_id,
    )

    await session_module.dispose_engine()
    await engine.dispose()
    with contextlib.suppress(FileNotFoundError):
        import os

        os.remove(async_url.split("/")[-1])


@pytest.mark.asyncio
async def test_issue_then_refresh_rotates_token(wired) -> None:
    refresh, users, user_id = wired
    issue = IssueRefreshTokenHandler(refresh)
    info = await issue.handle(user_id)
    assert info.token and info.expires_at

    refresh_handler = RefreshAccessTokenHandler(refresh, users)
    result = await refresh_handler.handle(info.token)
    assert result["access_token"]
    # New refresh token was issued.
    assert result["refresh_token"] != info.token


@pytest.mark.asyncio
async def test_refresh_rejects_revoked_token(wired) -> None:
    from app.core.exceptions import BusinessError

    refresh, users, user_id = wired
    issue = IssueRefreshTokenHandler(refresh)
    info = await issue.handle(user_id)
    logout = LogoutHandler(refresh)
    await logout.handle(info.token)

    refresh_handler = RefreshAccessTokenHandler(refresh, users)
    with pytest.raises(BusinessError):
        await refresh_handler.handle(info.token)


@pytest.mark.asyncio
async def test_revoke_all_for_user(wired) -> None:
    refresh, _, user_id = wired
    issue = IssueRefreshTokenHandler(refresh)
    for _ in range(3):
        await issue.handle(user_id)

    handler = LogoutAllHandler(refresh)
    count = await handler.handle(user_id)
    assert count == 3
