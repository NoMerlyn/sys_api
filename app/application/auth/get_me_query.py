"""GetCurrentUserQuery."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.interfaces.user_repository import IUserRepository
from app.core.exceptions import NotFoundException


@dataclass(frozen=True, slots=True)
class GetCurrentUserQuery:
    user_id: int


@dataclass(frozen=True, slots=True)
class CurrentUserDto:
    id: int
    username: str
    email: str
    name: str
    last_name: str
    roles: list[str]


class GetCurrentUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: GetCurrentUserQuery) -> CurrentUserDto:
        user = await self._users.find_by_id(cmd.user_id)
        if user is None:
            raise NotFoundException(f"Usuario {cmd.user_id} no encontrado")
        return CurrentUserDto(
            id=user.id,
            username=user.username,
            email=user.email,
            name=user.name,
            last_name=user.last_name,
            roles=[r.name for r in (user.roles or [])],
        )
