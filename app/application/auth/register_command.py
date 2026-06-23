"""RegisterUserCommand (admin-only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.interfaces.role_repository import IRoleRepository
from app.application.common.interfaces.user_repository import IUserRepository
from app.application.common.uow import uow
from app.core.exceptions import BusinessError
from app.core.security import hash_password


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    username: str
    name: str
    last_name: str
    email: str
    password: str
    cedula: str | None
    role_ids: list[int]


class RegisterUserHandler:
    def __init__(self, users: IUserRepository, roles: IRoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def handle(self, cmd: RegisterUserCommand) -> int:
        async with uow() as session:
            users = self._users.__class__(session)  # type: ignore[call-arg]
            existing = await users.find_by_email(cmd.email)
            if existing is not None:
                raise BusinessError(
                    f"Ya existe un usuario con email {cmd.email}",
                    details={"field": "email"},
                )
            existing_username = await users.find_by_username(cmd.username)
            if existing_username is not None:
                raise BusinessError(
                    f"Ya existe un usuario con username {cmd.username}",
                    details={"field": "username"},
                )
            from app.infrastructure.db.models.user import User  # local import

            user = User(
                username=cmd.username,
                name=cmd.name,
                last_name=cmd.last_name,
                cedula=cmd.cedula,
                email=cmd.email,
                password=hash_password(cmd.password),
            )
            user = await users.create(user)
            # Role assignment is done by the caller via AssignRolesCommand.
            return user.id
