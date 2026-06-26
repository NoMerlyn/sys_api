"""Users + roles + error-logs router (admin-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.application.common.uow import uow
from app.application.users import (
    AssignRolesCommand,
    AssignRolesDto,
    AssignRolesHandler,
    CreateUserCommand,
    CreateUserDto,
    CreateUserHandler,
    DeleteUserCommand,
    DeleteUserHandler,
    GetErrorLogsHandler,
    GetErrorLogsQuery,
    GetRolesHandler,
    GetRolesQuery,
    GetUserHandler,
    GetUserQuery,
    GetUserRolesHandler,
    GetUserRolesQuery,
    GetUsersHandler,
    GetUsersQuery,
    UpdateUserCommand,
    UpdateUserDto,
    UpdateUserHandler,
    UserResponseDto,
)
from app.core.pagination import parse_page
from app.presentation.deps import CurrentUserDep, require_role

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(require_role("ADMINISTRATOR"))]
)


@router.get("", response_model=dict)
async def list_users(
    _: CurrentUserDep,
    page: int | None = Query(default=None),
    limit: int | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict:
    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = GetUsersHandler(SqlUserRepository(session))
        rows, total = await handler.handle(
            GetUsersQuery(page=parse_page(page, limit), search=search)
        )
    return {
        "data": [r.model_dump() for r in rows],
        "total": total,
    }


@router.get("/roles/all", response_model=list[dict])
async def list_all_roles(_: CurrentUserDep) -> list[dict]:
    async with uow() as session:
        from app.infrastructure.repositories.role_repository import SqlRoleRepository

        handler = GetRolesHandler(SqlRoleRepository(session))
        rows = await handler.handle(GetRolesQuery())
    return [r.model_dump() for r in rows]


@router.get("/logs/errors", response_model=dict)
async def list_error_logs(
    _: CurrentUserDep,
    page: int | None = Query(default=None),
    limit: int | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict:
    async with uow() as session:
        from app.infrastructure.repositories.error_log_repository import (
            SqlErrorLogRepository,
        )

        handler = GetErrorLogsHandler(SqlErrorLogRepository(session))
        rows, total = await handler.handle(
            GetErrorLogsQuery(page=parse_page(page, limit), search=search)
        )
    return {
        "data": [r.model_dump() for r in rows],
        "total": total,
    }


@router.get("/{user_id}", response_model=UserResponseDto)
async def get_user(_: CurrentUserDep, user_id: int) -> UserResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = GetUserHandler(SqlUserRepository(session))
        return await handler.handle(GetUserQuery(user_id=user_id))


@router.post("", response_model=UserResponseDto, status_code=status.HTTP_201_CREATED)
async def create_user(currentUser: CurrentUserDep, payload: CreateUserDto) -> UserResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.role_repository import SqlRoleRepository
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = CreateUserHandler(SqlUserRepository(session), SqlRoleRepository(session))
        user_id = await handler.handle(CreateUserCommand(dto=payload))
        
        # Audit user creation
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="CREATE",
                entity="USER",
                entity_id=user_id,
                user_id=currentUser.id,
                detail=json.dumps(payload.model_dump(exclude={"password"}), ensure_ascii=False),
            )
            
        me_handler = GetUserHandler(SqlUserRepository(session))
        return await me_handler.handle(GetUserQuery(user_id=user_id))


@router.put("/{user_id}", response_model=UserResponseDto)
async def update_user(currentUser: CurrentUserDep, user_id: int, payload: UpdateUserDto) -> UserResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository
        repo = SqlUserRepository(session)
        
        old_user = await repo.find_by_id(user_id)
        before_state = {}
        if old_user:
            before_state = {
                "name": old_user.name,
                "last_name": old_user.last_name,
                "cedula": old_user.cedula,
                "email": old_user.email,
                "is_active": old_user.is_active,
            }

        handler = UpdateUserHandler(repo)
        res = await handler.handle(UpdateUserCommand(user_id=user_id, dto=payload))
        
        after_state = {
            "name": res.name,
            "last_name": res.last_name,
            "cedula": res.cedula,
            "email": res.email,
            "is_active": res.is_active,
        }
        
        # Audit user update
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="UPDATE",
                entity="USER",
                entity_id=user_id,
                user_id=currentUser.id,
                detail=json.dumps({
                    "before": before_state,
                    "after": after_state
                }, ensure_ascii=False),
            )
            
        return res


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(currentUser: CurrentUserDep, user_id: int) -> None:
    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = DeleteUserHandler(SqlUserRepository(session))
        await handler.handle(DeleteUserCommand(user_id=user_id))
        
        # Audit user status change (soft delete)
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="STATUS_CHANGE",
                entity="USER",
                entity_id=user_id,
                user_id=currentUser.id,
                detail=json.dumps({"is_active": False}, ensure_ascii=False),
            )


@router.post("/{user_id}/unlock", status_code=status.HTTP_204_NO_CONTENT)
async def unlock_user(_: CurrentUserDep, user_id: int) -> None:
    from app.application.auth import UnlockUserCommand, UnlockUserHandler

    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = UnlockUserHandler(SqlUserRepository(session))
        await handler.handle(UnlockUserCommand(user_id=user_id))


@router.get("/{user_id}/roles", response_model=list[dict])
async def get_user_roles(_: CurrentUserDep, user_id: int) -> list[dict]:
    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = GetUserRolesHandler(SqlUserRepository(session))
        rows = await handler.handle(GetUserRolesQuery(user_id=user_id))
    return [r.model_dump() for r in rows]


@router.put("/{user_id}/roles", response_model=UserResponseDto)
async def assign_roles(currentUser: CurrentUserDep, user_id: int, payload: AssignRolesDto) -> UserResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.role_repository import SqlRoleRepository
        from app.infrastructure.repositories.user_repository import SqlUserRepository
        repo = SqlUserRepository(session)
        
        old_user = await repo.find_by_id(user_id)
        before_state = {}
        if old_user:
            before_state = {
                "roles": [r.name for r in (old_user.roles or [])]
            }

        handler = AssignRolesHandler(repo, SqlRoleRepository(session))
        res = await handler.handle(AssignRolesCommand(user_id=user_id, role_ids=payload.role_ids))
        
        after_state = {
            "roles": res.roles
        }
        
        # Audit user roles update
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="UPDATE",
                entity="USER",
                entity_id=user_id,
                user_id=currentUser.id,
                detail=json.dumps({
                    "before": before_state,
                    "after": after_state
                }, ensure_ascii=False),
            )
            
        return res
