"""Clients router (admin + seller)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.application.clients import (
    ClientResponseDto,
    CreateClientCommand,
    CreateClientDto,
    CreateClientHandler,
    DeleteClientCommand,
    DeleteClientHandler,
    GetClientHandler,
    GetClientQuery,
    ListClientsHandler,
    ListClientsQuery,
    UpdateClientCommand,
    UpdateClientDto,
    UpdateClientHandler,
)
from app.application.common.uow import uow
from app.core.pagination import parse_page
from app.presentation.deps import CurrentUserDep, require_role

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=dict)
async def list_clients(
    _: CurrentUserDep,
    page: int | None = Query(default=None),
    limit: int | None = Query(default=None),
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> dict:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        handler = ListClientsHandler(SqlClientRepository(session))
        rows, total = await handler.handle(
            ListClientsQuery(page=parse_page(page, limit), search=search, is_active=is_active)
        )
    return {"data": [r.model_dump() for r in rows], "total": total}


@router.get("/{client_id}", response_model=ClientResponseDto)
async def get_client(_: CurrentUserDep, client_id: int) -> ClientResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        handler = GetClientHandler(SqlClientRepository(session))
        return await handler.handle(GetClientQuery(client_id=client_id))


@router.post("", response_model=ClientResponseDto, status_code=status.HTTP_201_CREATED)
async def create_client(user: CurrentUserDep, payload: CreateClientDto) -> ClientResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        create_h = CreateClientHandler(SqlClientRepository(session))
        client_id = await create_h.handle(CreateClientCommand(dto=payload))
        
        # Audit creation
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="CREATE",
                entity="CLIENT",
                entity_id=client_id,
                user_id=user.id,
                detail=json.dumps(payload.model_dump(), ensure_ascii=False),
            )
            
        get_h = GetClientHandler(SqlClientRepository(session))
        return await get_h.handle(GetClientQuery(client_id=client_id))


@router.put(
    "/{client_id}",
    response_model=ClientResponseDto,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def update_client(
    user: CurrentUserDep, client_id: int, payload: UpdateClientDto
) -> ClientResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository
        repo = SqlClientRepository(session)
        
        old_client = await repo.find_by_id(client_id)
        before_state = {}
        if old_client:
            before_state = {
                "first_name": old_client.first_name,
                "last_name": old_client.last_name,
                "cedula": old_client.cedula,
                "phone": old_client.phone,
                "address": old_client.address,
                "email": old_client.email,
                "is_active": old_client.is_active,
            }

        handler = UpdateClientHandler(repo)
        res = await handler.handle(UpdateClientCommand(client_id=client_id, dto=payload))
        
        after_state = {
            "first_name": res.first_name,
            "last_name": res.last_name,
            "cedula": res.cedula,
            "phone": res.phone,
            "address": res.address,
            "email": res.email,
            "is_active": res.is_active,
        }
        
        # Audit update
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="UPDATE",
                entity="CLIENT",
                entity_id=client_id,
                user_id=user.id,
                detail=json.dumps({
                    "before": before_state,
                    "after": after_state
                }, ensure_ascii=False),
            )
            
        return res


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def delete_client(user: CurrentUserDep, client_id: int) -> None:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        handler = DeleteClientHandler(SqlClientRepository(session))
        await handler.handle(DeleteClientCommand(client_id=client_id))
        
        # Audit status change (soft delete)
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="STATUS_CHANGE",
                entity="CLIENT",
                entity_id=client_id,
                user_id=user.id,
                detail=json.dumps({"is_active": False}, ensure_ascii=False),
            )
