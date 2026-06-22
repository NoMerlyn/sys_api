"""Roles router (admin-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.common.uow import uow
from app.application.users import GetRolesHandler, GetRolesQuery, RoleResponseDto
from app.presentation.deps import require_role

router = APIRouter(
    prefix="/roles", tags=["roles"], dependencies=[Depends(require_role("ADMINISTRATOR"))]
)


@router.get("", response_model=list[RoleResponseDto])
async def list_roles() -> list[RoleResponseDto]:
    async with uow() as session:
        from app.infrastructure.repositories.role_repository import SqlRoleRepository

        handler = GetRolesHandler(SqlRoleRepository(session))
        rows = await handler.handle(GetRolesQuery())
    return [RoleResponseDto(**r.model_dump()) for r in rows]
