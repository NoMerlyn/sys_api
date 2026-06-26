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
async def create_tax(user: CurrentUserDep, payload: CreateTaxDto) -> TaxResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository
        repo = SqlTaxRepository(session)
        create_h = CreateTaxHandler(repo)
        tax_id = await create_h.handle(CreateTaxCommand(dto=payload))
        
        # Audit creation
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="CREATE",
                entity="TAX",
                entity_id=tax_id,
                user_id=user.id,
                detail=json.dumps(payload.model_dump(), ensure_ascii=False),
            )
            
        get_h = GetTaxHandler(repo)
        return await get_h.handle(GetTaxQuery(tax_id=tax_id))


@router.put(
    "/{tax_id}",
    response_model=TaxResponseDto,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def update_tax(user: CurrentUserDep, tax_id: int, payload: UpdateTaxDto) -> TaxResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository
        repo = SqlTaxRepository(session)
        
        old_tax = await repo.find_by_id(tax_id)
        before_state = {}
        if old_tax:
            before_state = {
                "name": old_tax.name,
                "current_rate": float(old_tax.current_rate),
                "is_active": old_tax.is_active,
            }
            
        handler = UpdateTaxHandler(repo)
        res = await handler.handle(UpdateTaxCommand(tax_id=tax_id, dto=payload))
        
        after_state = {
            "name": res.name,
            "current_rate": float(res.current_rate),
            "is_active": res.is_active,
        }
        
        # Audit update
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="UPDATE",
                entity="TAX",
                entity_id=tax_id,
                user_id=user.id,
                detail=json.dumps({
                    "before": before_state,
                    "after": after_state
                }, ensure_ascii=False),
            )
        return res


@router.delete(
    "/{tax_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def delete_tax(user: CurrentUserDep, tax_id: int) -> None:
    async with uow() as session:
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository
        repo = SqlTaxRepository(session)
        
        handler = DeleteTaxHandler(repo)
        await handler.handle(DeleteTaxCommand(tax_id=tax_id))
        
        # Audit status change (soft delete)
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="STATUS_CHANGE",
                entity="TAX",
                entity_id=tax_id,
                user_id=user.id,
                detail=json.dumps({"is_active": False}, ensure_ascii=False),
            )
