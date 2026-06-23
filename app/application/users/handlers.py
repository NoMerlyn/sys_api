"""User use-case handlers (commands + queries)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.common.interfaces.error_log_repository import IErrorLogRepository
from app.application.common.interfaces.role_repository import IRoleRepository
from app.application.common.interfaces.user_repository import IUserRepository
from app.application.common.uow import uow
from app.application.users.dto import (
    CreateUserDto,
    ErrorLogResponseDto,
    RoleResponseDto,
    UpdateUserDto,
    UserResponseDto,
)
from app.core.exceptions import BusinessError, NotFoundError
from app.core.pagination import Page
from app.core.security import hash_password


def _to_user_dto(user: Any) -> UserResponseDto:
    return UserResponseDto(
        id=user.id,
        username=user.username,
        email=user.email,
        name=user.name,
        last_name=user.last_name,
        cedula=user.cedula,
        is_active=user.is_active,
        roles=[r.name for r in (user.roles or [])],
    )


@dataclass(frozen=True, slots=True)
class GetUsersQuery:
    page: Page
    search: str | None = None


class GetUsersHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: GetUsersQuery) -> tuple[list[UserResponseDto], int]:
        async with uow() as session:
            users = self._users.__class__(session)
            rows, total = await users.find_all(cmd.page, cmd.search)
            return [_to_user_dto(u) for u in rows], total


@dataclass(frozen=True, slots=True)
class GetUserQuery:
    user_id: int


class GetUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: GetUserQuery) -> UserResponseDto:
        async with uow() as session:
            users = self._users.__class__(session)
            user = await users.find_by_id(cmd.user_id)
            if user is None:
                raise NotFoundError(f"Usuario {cmd.user_id} no encontrado")
            return _to_user_dto(user)


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    dto: CreateUserDto


class CreateUserHandler:
    def __init__(self, users: IUserRepository, roles: IRoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def handle(self, cmd: CreateUserCommand) -> int:
        async with uow() as session:
            users = self._users.__class__(session)
            if await users.find_by_email(cmd.dto.email) is not None:
                raise BusinessError(
                    f"Email duplicado: {cmd.dto.email}", details={"field": "email"}
                )
            if await users.find_by_username(cmd.dto.username) is not None:
                raise BusinessError(
                    f"Username duplicado: {cmd.dto.username}",
                    details={"field": "username"},
                )
            from app.infrastructure.db.models.user import User

            user = User(
                username=cmd.dto.username,
                name=cmd.dto.name,
                last_name=cmd.dto.last_name,
                cedula=cmd.dto.cedula,
                email=cmd.dto.email,
                password=hash_password(cmd.dto.password),
            )
            user = await users.create(user)
            if cmd.dto.role_ids:
                await self._assign_roles(session, user.id, cmd.dto.role_ids)
            return user.id

    async def _assign_roles(self, session: Any, user_id: int, role_ids: list[int]) -> None:
        from app.infrastructure.db.models.user_role import UserRole

        for role_id in role_ids:
            session.add(UserRole(user_id=user_id, role_id=role_id))
        await session.flush()


@dataclass(frozen=True, slots=True)
class UpdateUserCommand:
    user_id: int
    dto: UpdateUserDto


class UpdateUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: UpdateUserCommand) -> UserResponseDto:
        async with uow() as session:
            users = self._users.__class__(session)
            user = await users.find_by_id(cmd.user_id)
            if user is None:
                raise NotFoundError(f"Usuario {cmd.user_id} no encontrado")
            if cmd.dto.name is not None:
                user.name = cmd.dto.name
            if cmd.dto.last_name is not None:
                user.last_name = cmd.dto.last_name
            if cmd.dto.cedula is not None:
                user.cedula = cmd.dto.cedula
            if cmd.dto.email is not None:
                user.email = cmd.dto.email
            if cmd.dto.is_active is not None:
                user.is_active = cmd.dto.is_active
            await users.update(user)
            return _to_user_dto(user)


@dataclass(frozen=True, slots=True)
class DeleteUserCommand:
    user_id: int


class DeleteUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: DeleteUserCommand) -> None:
        async with uow() as session:
            users = self._users.__class__(session)
            await users.soft_delete(cmd.user_id)


@dataclass(frozen=True, slots=True)
class AssignRolesCommand:
    user_id: int
    role_ids: list[int]


class AssignRolesHandler:
    def __init__(self, users: IUserRepository, roles: IRoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def handle(self, cmd: AssignRolesCommand) -> UserResponseDto:
        async with uow() as session:
            users = self._users.__class__(session)
            user = await users.find_by_id(cmd.user_id)
            if user is None:
                raise NotFoundError(f"Usuario {cmd.user_id} no encontrado")
            from sqlalchemy import delete

            from app.infrastructure.db.models.user_role import UserRole

            await session.execute(delete(UserRole).where(UserRole.user_id == cmd.user_id))
            for role_id in cmd.role_ids:
                session.add(UserRole(user_id=cmd.user_id, role_id=role_id))
            await session.flush()
            refreshed = await users.find_by_id(cmd.user_id)
            return _to_user_dto(refreshed)


@dataclass(frozen=True, slots=True)
class GetRolesQuery:
    pass


class GetRolesHandler:
    def __init__(self, roles: IRoleRepository) -> None:
        self._roles = roles

    async def handle(self, cmd: GetRolesQuery) -> list[RoleResponseDto]:
        async with uow() as session:
            roles = self._roles.__class__(session)
            rows = await roles.find_all()
            return [RoleResponseDto(id=r.id, name=r.name, description=r.description) for r in rows]


@dataclass(frozen=True, slots=True)
class GetUserRolesQuery:
    user_id: int


class GetUserRolesHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: GetUserRolesQuery) -> list[RoleResponseDto]:
        async with uow() as session:
            users = self._users.__class__(session)
            user = await users.find_by_id(cmd.user_id)
            if user is None:
                raise NotFoundError(f"Usuario {cmd.user_id} no encontrado")
            return [
                RoleResponseDto(id=r.id, name=r.name, description=r.description)
                for r in (user.roles or [])
            ]


@dataclass(frozen=True, slots=True)
class GetErrorLogsQuery:
    page: Page
    search: str | None = None


class GetErrorLogsHandler:
    def __init__(self, error_logs: IErrorLogRepository) -> None:
        self._logs = error_logs

    async def handle(self, cmd: GetErrorLogsQuery) -> tuple[list[ErrorLogResponseDto], int]:
        async with uow() as session:
            logs = self._logs.__class__(session)
            rows, total = await logs.find_all(cmd.page, cmd.search)
            return [
                ErrorLogResponseDto(
                    id=row.id,
                    message=row.message,
                    exception_type=row.exception_type,
                    user_id=row.user_id,
                    path=row.path,
                    source=row.source,
                    created_at=row.created_at.isoformat() if row.created_at else "",
                )
                for row in rows
            ], total
