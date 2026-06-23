"""Clients use-case handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.clients.dto import (
    ClientResponseDto,
    CreateClientDto,
    UpdateClientDto,
)
from app.application.common.interfaces.client_repository import IClientRepository
from app.application.common.uow import uow
from app.core.exceptions import NotFoundError
from app.core.pagination import Page


def _to_dto(c: Any) -> ClientResponseDto:
    return ClientResponseDto(
        id=c.id,
        first_name=c.first_name,
        last_name=c.last_name,
        cedula=c.cedula,
        phone=c.phone,
        address=c.address,
        email=c.email,
        is_active=c.is_active,
    )


@dataclass(frozen=True, slots=True)
class ListClientsQuery:
    page: Page
    search: str | None = None


class ListClientsHandler:
    def __init__(self, clients: IClientRepository) -> None:
        self._clients = clients

    async def handle(self, cmd: ListClientsQuery) -> tuple[list[ClientResponseDto], int]:
        async with uow() as session:
            clients = self._clients.__class__(session)
            rows, total = await clients.find_all(cmd.page, cmd.search)
            return [_to_dto(c) for c in rows], total


@dataclass(frozen=True, slots=True)
class GetClientQuery:
    client_id: int


class GetClientHandler:
    def __init__(self, clients: IClientRepository) -> None:
        self._clients = clients

    async def handle(self, cmd: GetClientQuery) -> ClientResponseDto:
        async with uow() as session:
            clients = self._clients.__class__(session)
            c = await clients.find_by_id(cmd.client_id)
            if c is None:
                raise NotFoundError(f"Cliente {cmd.client_id} no encontrado")
            return _to_dto(c)


@dataclass(frozen=True, slots=True)
class CreateClientCommand:
    dto: CreateClientDto


class CreateClientHandler:
    def __init__(self, clients: IClientRepository) -> None:
        self._clients = clients

    async def handle(self, cmd: CreateClientCommand) -> int:
        async with uow() as session:
            clients = self._clients.__class__(session)
            from app.infrastructure.db.models.client import Client

            row = Client(
                first_name=cmd.dto.first_name,
                last_name=cmd.dto.last_name,
                cedula=cmd.dto.cedula,
                phone=cmd.dto.phone,
                address=cmd.dto.address,
                email=cmd.dto.email,
            )
            row = await clients.create(row)
            return row.id


@dataclass(frozen=True, slots=True)
class UpdateClientCommand:
    client_id: int
    dto: UpdateClientDto


class UpdateClientHandler:
    def __init__(self, clients: IClientRepository) -> None:
        self._clients = clients

    async def handle(self, cmd: UpdateClientCommand) -> ClientResponseDto:
        async with uow() as session:
            clients = self._clients.__class__(session)
            c = await clients.find_by_id(cmd.client_id)
            if c is None:
                raise NotFoundError(f"Cliente {cmd.client_id} no encontrado")
            for field in ("first_name", "last_name", "cedula", "phone", "address", "email"):
                value = getattr(cmd.dto, field)
                if value is not None:
                    setattr(c, field, value)
            if cmd.dto.is_active is not None:
                c.is_active = cmd.dto.is_active
            await clients.update(c)
            return _to_dto(c)


@dataclass(frozen=True, slots=True)
class DeleteClientCommand:
    client_id: int


class DeleteClientHandler:
    def __init__(self, clients: IClientRepository) -> None:
        self._clients = clients

    async def handle(self, cmd: DeleteClientCommand) -> None:
        async with uow() as session:
            clients = self._clients.__class__(session)
            await clients.soft_delete(cmd.client_id)
