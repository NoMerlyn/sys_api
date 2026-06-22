"""Clients router (admin + seller)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

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
from app.presentation.deps import CurrentUserDep

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=dict)
async def list_clients(
    _: CurrentUserDep,
    page: int | None = Query(default=None),
    limit: int | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        handler = ListClientsHandler(SqlClientRepository(session))
        rows, total = await handler.handle(
            ListClientsQuery(page=parse_page(page, limit), search=search)
        )
    return {"data": [r.model_dump() for r in rows], "total": total}


@router.get("/{client_id}", response_model=ClientResponseDto)
async def get_client(_: CurrentUserDep, client_id: int) -> ClientResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        handler = GetClientHandler(SqlClientRepository(session))
        return await handler.handle(GetClientQuery(client_id=client_id))


@router.post("", response_model=ClientResponseDto, status_code=status.HTTP_201_CREATED)
async def create_client(_: CurrentUserDep, payload: CreateClientDto) -> ClientResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        create_h = CreateClientHandler(SqlClientRepository(session))
        client_id = await create_h.handle(CreateClientCommand(dto=payload))
        get_h = GetClientHandler(SqlClientRepository(session))
        return await get_h.handle(GetClientQuery(client_id=client_id))


@router.put("/{client_id}", response_model=ClientResponseDto)
async def update_client(
    _: CurrentUserDep, client_id: int, payload: UpdateClientDto
) -> ClientResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        handler = UpdateClientHandler(SqlClientRepository(session))
        return await handler.handle(UpdateClientCommand(client_id=client_id, dto=payload))


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(_: CurrentUserDep, client_id: int) -> None:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository

        handler = DeleteClientHandler(SqlClientRepository(session))
        await handler.handle(DeleteClientCommand(client_id=client_id))
