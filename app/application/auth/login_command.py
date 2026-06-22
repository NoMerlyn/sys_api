"""LoginCommand handler.

Flow (mirrors Proyecto_A/pos-api):
  1. Find user by email.
  2. Verify password (bcrypt).
  3. On success: reset failed_attempts, clear blocked_at, issue JWT.
  4. On failure: increment failed_attempts; if >= max, set blocked_at.

Returns (access_token, expires_in_seconds). Raises:
  - AuthException on invalid credentials (401).
  - AccountBlockedException if the user is currently blocked (423).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.interfaces.user_repository import IUserRepository
from app.application.common.uow import uow
from app.config import get_settings
from app.core.exceptions import (
    AccountBlockedException,
    AuthException,
)
from app.core.security import (
    create_access_token,
    verify_password,
)


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    expires_in: int


class LoginHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: LoginCommand) -> LoginResult:
        settings = get_settings()
        async with uow() as session:
            users = self._users.__class__(session)
            user = await users.find_by_email(cmd.email)
            if user is None:
                raise AuthException("Credenciales inválidas")

            # Re-load inside this session (the injected repo was created outside).
            user = await users.find_by_email(cmd.email)
            assert user is not None

            if user.blocked_at is not None:
                raise AccountBlockedException("Cuenta bloqueada tras múltiples intentos fallidos")

            if not verify_password(cmd.password, user.password):
                attempts = await users.increment_failed_attempts(user.id)
                if attempts >= settings.login_max_failed_attempts:
                    await users.block(user.id)
                    raise AccountBlockedException(
                        "Cuenta bloqueada tras múltiples intentos fallidos"
                    )
                raise AuthException("Credenciales inválidas")

            # Success
            await users.reset_failed_attempts(user.id)
            roles = [r.name for r in (user.roles or [])]
            token, expires_in = create_access_token(
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
            return LoginResult(access_token=token, expires_in=expires_in)
