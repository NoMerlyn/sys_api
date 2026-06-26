"""Refresh token use cases.

The login command now issues both an access token (short-lived JWT)
and a refresh token (long-lived, opaque, stored server-side). The
refresh command validates the stored token and mints a new access
token without re-asking for credentials.

The logout command revokes a single refresh token. The
revoke_all_sessions handler nukes every refresh token for a user
(useful for "logout everywhere" or after a password change).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.common.interfaces.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.application.common.interfaces.user_repository import IUserRepository
from app.application.common.uow import uow
from app.config import get_settings
from app.core.security import create_access_token
from app.domain.exceptions.business import BusinessError as BusinessException


def _new_token() -> str:
    """URL-safe random token, 64 bytes = 128 hex chars of entropy."""
    return secrets.token_urlsafe(64)


@dataclass(frozen=True, slots=True)
class RefreshTokenInfo:
    token: str
    expires_at: datetime


class IssueRefreshTokenHandler:
    """Create a refresh token for `user_id` and persist it."""

    def __init__(self, refresh: RefreshTokenRepository) -> None:
        self._refresh = refresh

    async def handle(
        self,
        user_id: int,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshTokenInfo:
        token = _new_token()
        # Default 30 days. Configurable via env if needed.
        expires_at = datetime.now(tz=UTC) + timedelta(days=30)
        async with uow() as session:
            repo = self._refresh.__class__(session)  # type: ignore[call-arg]
            await repo.add(
                token=token,
                user_id=user_id,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        return RefreshTokenInfo(token=token, expires_at=expires_at)


class RefreshAccessTokenHandler:
    """Exchange a valid refresh token for a new access token (+ rotated refresh)."""

    def __init__(
        self,
        refresh: RefreshTokenRepository,
        users: IUserRepository,
    ) -> None:
        self._refresh = refresh
        self._users = users

    async def handle(self, refresh_token: str, *, ip_address: str | None = None) -> dict:
        async with uow() as session:
            refresh = self._refresh.__class__(session)  # type: ignore[call-arg]
            row = await refresh.find_active(refresh_token)
            if row is None:
                raise BusinessException("Refresh token inválido o expirado")

            users = self._users.__class__(session)  # type: ignore[call-arg]
            user = await users.find_by_id(row["user_id"])
            if user is None:
                # User was deleted between issue and refresh.
                raise BusinessException("Refresh token inválido")

            # Rotate: revoke the old token and issue a new one.
            await refresh.revoke(refresh_token)
            new_token = _new_token()
            new_expires = datetime.now(tz=UTC) + timedelta(days=30)
            await refresh.add(
                token=new_token,
                user_id=user.id,
                expires_at=new_expires,
                ip_address=ip_address,
            )

        # Mint a new access token.
        settings = get_settings()
        roles = [r.name for r in (user.roles or [])]
        access_token, expires_in = create_access_token(
            subject=str(user.id),
            secret=settings.jwt_secret,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            algorithm=settings.jwt_algorithm,
            ttl_seconds=settings.jwt_ttl_seconds,
            extra_claims={
                "username": user.username,
                "email": user.email,
                "roles": roles,
            },
        )
        return {
            "access_token": access_token,
            "expires_in": expires_in,
            "refresh_token": new_token,
        }


class LogoutHandler:
    """Revoke a single refresh token (logout this device)."""

    def __init__(self, refresh: RefreshTokenRepository) -> None:
        self._refresh = refresh

    async def handle(self, refresh_token: str) -> None:
        async with uow() as session:
            refresh = self._refresh.__class__(session)  # type: ignore[call-arg]
            await refresh.revoke(refresh_token)


class LogoutAllHandler:
    """Revoke every refresh token for a user (logout everywhere)."""

    def __init__(self, refresh: RefreshTokenRepository) -> None:
        self._refresh = refresh

    async def handle(self, user_id: int) -> int:
        async with uow() as session:
            refresh = self._refresh.__class__(session)  # type: ignore[call-arg]
            return await refresh.revoke_all_for_user(user_id)


# Re-exports (back-compat with the old __init__.py that re-exported
# every handler from the corresponding module).
from app.application.auth.get_me_query import (  # noqa: E402,F401
    CurrentUserDto,
    GetCurrentUserHandler,
    GetCurrentUserQuery,
)
from app.application.auth.login_command import (  # noqa: E402,F401
    LoginCommand,
    LoginHandler,
    LoginResult,
)
from app.application.auth.register_command import (  # noqa: E402,F401
    RegisterUserCommand,
    RegisterUserHandler,
)
from app.application.auth.unlock_command import (  # noqa: E402,F401
    UnlockUserCommand,
    UnlockUserHandler,
)
