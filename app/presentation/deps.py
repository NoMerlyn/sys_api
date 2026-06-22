"""FastAPI dependencies: auth, role guards, repository factories, pagination."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError

from app.config import Settings, get_settings
from app.core.security import decode_access_token


class CurrentUser:
    __slots__ = ("id", "username", "email", "roles")

    def __init__(self, user_id: int, username: str, email: str, roles: list[str]) -> None:
        self.id = user_id
        self.username = username
        self.email = email
        self.roles = roles

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token Bearer requerido"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[7:].strip()


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> CurrentUser:
    token = _parse_bearer(authorization)
    try:
        payload = decode_access_token(
            token,
            secret=settings.jwt_secret,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            algorithm=settings.jwt_algorithm,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": f"Token inválido: {exc}"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return CurrentUser(
        user_id=int(payload["sub"]),
        username=payload.get("username", ""),
        email=payload.get("email", ""),
        roles=list(payload.get("roles", [])),
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_role(role: str):
    """Build a dependency that asserts the current user has the given role."""

    def _checker(user: CurrentUserDep) -> CurrentUser:
        if not user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Rol requerido: {role}",
                },
            )
        return user

    return _checker
