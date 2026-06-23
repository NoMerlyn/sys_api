"""UnlockUserCommand (admin-only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.interfaces.user_repository import IUserRepository
from app.application.common.uow import uow
from app.core.exceptions import NotFoundError


@dataclass(frozen=True, slots=True)
class UnlockUserCommand:
    user_id: int


class UnlockUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: UnlockUserCommand) -> None:
        async with uow() as session:
            users = self._users.__class__(session)  # type: ignore[call-arg]
            user = await users.find_by_id(cmd.user_id)
            if user is None:
                raise NotFoundError(f"Usuario {cmd.user_id} no encontrado")
            await users.reset_failed_attempts(user.id)
