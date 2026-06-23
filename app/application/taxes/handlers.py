"""Taxes use-case handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.common.interfaces.tax_repository import ITaxRepository
from app.application.common.uow import uow
from app.application.taxes.dto import CreateTaxDto, TaxResponseDto, UpdateTaxDto
from app.core.exceptions import NotFoundError


def _to_dto(t: Any) -> TaxResponseDto:
    return TaxResponseDto(id=t.id, name=t.name, current_rate=t.current_rate)


@dataclass(frozen=True, slots=True)
class ListTaxesQuery:
    pass


class ListTaxesHandler:
    def __init__(self, taxes: ITaxRepository) -> None:
        self._taxes = taxes

    async def handle(self, cmd: ListTaxesQuery) -> list[TaxResponseDto]:
        async with uow() as session:
            taxes = self._taxes.__class__(session)
            rows = await taxes.find_all()
            return [_to_dto(t) for t in rows]


@dataclass(frozen=True, slots=True)
class GetTaxQuery:
    tax_id: int


class GetTaxHandler:
    def __init__(self, taxes: ITaxRepository) -> None:
        self._taxes = taxes

    async def handle(self, cmd: GetTaxQuery) -> TaxResponseDto:
        async with uow() as session:
            taxes = self._taxes.__class__(session)
            t = await taxes.find_by_id(cmd.tax_id)
            if t is None:
                raise NotFoundError(f"Impuesto {cmd.tax_id} no encontrado")
            return _to_dto(t)


@dataclass(frozen=True, slots=True)
class CreateTaxCommand:
    dto: CreateTaxDto


class CreateTaxHandler:
    def __init__(self, taxes: ITaxRepository) -> None:
        self._taxes = taxes

    async def handle(self, cmd: CreateTaxCommand) -> int:
        async with uow() as session:
            taxes = self._taxes.__class__(session)
            from app.infrastructure.db.models.tax import Tax

            row = Tax(name=cmd.dto.name, current_rate=cmd.dto.current_rate)
            row = await taxes.create(row)
            return row.id


@dataclass(frozen=True, slots=True)
class UpdateTaxCommand:
    tax_id: int
    dto: UpdateTaxDto


class UpdateTaxHandler:
    def __init__(self, taxes: ITaxRepository) -> None:
        self._taxes = taxes

    async def handle(self, cmd: UpdateTaxCommand) -> TaxResponseDto:
        async with uow() as session:
            taxes = self._taxes.__class__(session)
            t = await taxes.find_by_id(cmd.tax_id)
            if t is None:
                raise NotFoundError(f"Impuesto {cmd.tax_id} no encontrado")
            if cmd.dto.name is not None:
                t.name = cmd.dto.name
            if cmd.dto.current_rate is not None:
                t.current_rate = cmd.dto.current_rate
            await taxes.update(t)
            return _to_dto(t)


@dataclass(frozen=True, slots=True)
class DeleteTaxCommand:
    tax_id: int


class DeleteTaxHandler:
    def __init__(self, taxes: ITaxRepository) -> None:
        self._taxes = taxes

    async def handle(self, cmd: DeleteTaxCommand) -> None:
        async with uow() as session:
            taxes = self._taxes.__class__(session)
            await taxes.soft_delete(cmd.tax_id)
