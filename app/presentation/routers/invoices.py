"""Invoices router."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.application.common.uow import uow
from app.application.invoices import (
    ChangeInvoiceStatusCommand,
    ChangeInvoiceStatusDto,
    ChangeInvoiceStatusHandler,
    CreateInvoiceCommand,
    CreateInvoiceDto,
    CreateInvoiceHandler,
    GetInvoiceByNumberHandler,
    GetInvoiceByNumberQuery,
    GetInvoiceHandler,
    GetInvoiceQuery,
    GetInvoicesHandler,
    GetInvoicesQuery,
    InvoiceResponseDto,
    UpdateInvoiceCommand,
    UpdateInvoiceDto,
    UpdateInvoiceHandler,
)
from app.core.pagination import parse_page
from app.domain.value_objects.invoice_status import InvoiceStatus
from app.presentation.deps import CurrentUserDep

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _scope(rows: list[InvoiceResponseDto], user) -> list[InvoiceResponseDto]:
    if "ADMINISTRATOR" in user.roles:
        return rows
    return [r for r in rows if r.seller_id == user.id]


@router.get("", response_model=dict)
async def list_invoices(
    user: CurrentUserDep,
    page: int | None = Query(default=None),
    limit: int | None = Query(default=None),
    search: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
) -> dict:
    status_enum = None
    if status_:
        try:
            status_enum = InvoiceStatus(status_.upper())
        except ValueError:
            status_enum = None
    seller_id = None if "ADMINISTRATOR" in user.roles else user.id
    async with uow() as session:
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )

        handler = GetInvoicesHandler(SqlInvoiceRepository(session))
        rows, total = await handler.handle(
            GetInvoicesQuery(
                page=parse_page(page, limit),
                search=search,
                status=status_enum,
                seller_id=seller_id,
            )
        )
    scoped = _scope(rows, user)
    return {
        "data": [r.model_dump(mode="json") for r in scoped],
        "total": total if "ADMINISTRATOR" in user.roles else len(scoped),
    }


@router.get("/{invoice_id}", response_model=InvoiceResponseDto)
async def get_invoice(user: CurrentUserDep, invoice_id: int) -> InvoiceResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )

        handler = GetInvoiceHandler(SqlInvoiceRepository(session))
        invoice = await handler.handle(GetInvoiceQuery(invoice_id=invoice_id))
    if "ADMINISTRATOR" not in user.roles and invoice.seller_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    return invoice


@router.get("/by-number/{invoice_number}", response_model=InvoiceResponseDto)
async def get_invoice_by_number(user: CurrentUserDep, invoice_number: str) -> InvoiceResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )

        handler = GetInvoiceByNumberHandler(SqlInvoiceRepository(session))
        invoice = await handler.handle(GetInvoiceByNumberQuery(invoice_number=invoice_number))
    if "ADMINISTRATOR" not in user.roles and invoice.seller_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    return invoice


@router.post("", response_model=InvoiceResponseDto, status_code=status.HTTP_201_CREATED)
async def create_invoice(user: CurrentUserDep, payload: CreateInvoiceDto) -> InvoiceResponseDto:
    async with uow() as session:
        from app.application.audit import audit
        from app.infrastructure.repositories.client_repository import SqlClientRepository
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )
        from app.infrastructure.repositories.product_repository import (
            SqlProductRepository,
        )
        from app.infrastructure.repositories.tax_repository import SqlTaxRepository
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = CreateInvoiceHandler(
            SqlInvoiceRepository(session),
            SqlProductRepository(session),
            SqlClientRepository(session),
            SqlUserRepository(session),
            SqlTaxRepository(session),
        )
        invoice_id = await handler.handle(CreateInvoiceCommand(dto=payload, seller_id=user.id))
        # Audit the creation.
        async with audit(session) as log:
            await log.add(
                action="CREATE",
                entity="INVOICE",
                entity_id=invoice_id,
                user_id=user.id,
                detail=f"client_id={payload.client_id}, items={len(payload.items)}",
            )
        get_h = GetInvoiceHandler(SqlInvoiceRepository(session))
        return await get_h.handle(GetInvoiceQuery(invoice_id=invoice_id))


@router.patch("/{invoice_id}", response_model=InvoiceResponseDto)
async def update_invoice(
    user: CurrentUserDep, invoice_id: int, payload: UpdateInvoiceDto
) -> InvoiceResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.client_repository import SqlClientRepository
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )
        from app.infrastructure.repositories.product_repository import (
            SqlProductRepository,
        )

        handler = UpdateInvoiceHandler(
            SqlInvoiceRepository(session),
            SqlProductRepository(session),
            SqlClientRepository(session),
        )
        return await handler.handle(UpdateInvoiceCommand(invoice_id=invoice_id, dto=payload))


@router.patch("/{invoice_id}/status", response_model=InvoiceResponseDto)
async def change_invoice_status(
    user: CurrentUserDep, invoice_id: int, payload: ChangeInvoiceStatusDto
) -> InvoiceResponseDto:
    from fastapi import HTTPException

    if "ADMINISTRATOR" not in user.roles:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    async with uow() as session:
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )
        from app.infrastructure.repositories.product_repository import (
            SqlProductRepository,
        )
        from app.infrastructure.repositories.stock_movement_repository import (
            SqlStockMovementRepository,
        )

        handler = ChangeInvoiceStatusHandler(
            SqlInvoiceRepository(session),
            SqlProductRepository(session),
            SqlStockMovementRepository(session),
        )
        invoice = await handler.handle(
            ChangeInvoiceStatusCommand(invoice_id=invoice_id, dto=payload, actor_id=user.id)
        )
        # Audit the status change.
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="STATUS_CHANGE",
                entity="INVOICE",
                entity_id=invoice_id,
                user_id=user.id,
                detail=f"status={payload.status}, reason={payload.reason or ''}"[:255],
            )
        return invoice
