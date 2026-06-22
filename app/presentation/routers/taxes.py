"""Taxes router (admin manages, sellers can list for the POS UI)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.common.uow import uow
from app.application.taxes import (
    CreateTaxCommand,
    CreateTaxDto,
    CreateTaxHandler,
    DeleteTaxCommand,
    DeleteTaxHandler,
    GetTaxHandler,
    GetTaxQuery,
    ListTaxesHandler,
    ListTaxesQuery,
    TaxResponseDto,
    UpdateTaxCommand,
    UpdateTaxDto,
    UpdateTaxHandler,
)
from app.presentation.deps import CurrentUserDep, require_role

router = APIRouter(prefix="/taxes", tags=["taxes"])


@router.get("", response_model=list[TaxResponseDto])
async def list_taxes(_: CurrentUserDep) -> list[TaxResponseDto]:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository

        handler = ListTaxesHandler(SqlTaxRepository(session))
        rows = await handler.handle(ListTaxesQuery())
    return [TaxResponseDto(**r.model_dump(mode="json")) for r in rows]


@router.get("/{tax_id}", response_model=TaxResponseDto)
async def get_tax(_: CurrentUserDep, tax_id: int) -> TaxResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository

        handler = GetTaxHandler(SqlTaxRepository(session))
        return await handler.handle(GetTaxQuery(tax_id=tax_id))


@router.post(
    "",
    response_model=TaxResponseDto,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def create_tax(_: CurrentUserDep, payload: CreateTaxDto) -> TaxResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository

        create_h = CreateTaxHandler(SqlTaxRepository(session))
        tax_id = await create_h.handle(CreateTaxCommand(dto=payload))
        get_h = GetTaxHandler(SqlTaxRepository(session))
        return await get_h.handle(GetTaxQuery(tax_id=tax_id))


@router.put(
    "/{tax_id}",
    response_model=TaxResponseDto,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def update_tax(_: CurrentUserDep, tax_id: int, payload: UpdateTaxDto) -> TaxResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository

        handler = UpdateTaxHandler(SqlTaxRepository(session))
        return await handler.handle(UpdateTaxCommand(tax_id=tax_id, dto=payload))


@router.delete(
    "/{tax_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def delete_tax(_: CurrentUserDep, tax_id: int) -> None:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository

        handler = DeleteTaxHandler(SqlTaxRepository(session))
        await handler.handle(DeleteTaxCommand(tax_id=tax_id))
