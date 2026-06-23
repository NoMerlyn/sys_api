"""Invoices use-case handlers.

The state machine lives in `app.domain.value_objects.invoice_status`; every
command/query calls `can_transition` before mutating.

Total calculation (mirrors Proyecto_A):
  subtotal = sum(qty * unit_price_snapshot)
  tax_total = sum(line.tax_amount_snapshot)
  total = subtotal + tax_total
All money values are stored as `Numeric(12, 2)` and rounded to 2dp at write.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.application.common.interfaces.client_repository import IClientRepository
from app.application.common.interfaces.invoice_repository import IInvoiceRepository
from app.application.common.interfaces.product_repository import IProductRepository
from app.application.common.interfaces.stock_movement_repository import (
    IStockMovementRepository,
)
from app.application.common.interfaces.tax_repository import ITaxRepository
from app.application.common.interfaces.user_repository import IUserRepository
from app.application.common.uow import uow
from app.application.invoices.dto import (
    ChangeInvoiceStatusDto,
    CreateInvoiceDto,
    InvoiceResponseDto,
    UpdateInvoiceDto,
)
from app.core.exceptions import BusinessError, NotFoundError
from app.core.pagination import Page
from app.domain.value_objects.invoice_status import (
    InvoiceStatus,
    can_transition,
)
from app.domain.value_objects.movement_type import MovementType


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_dto(inv: Any) -> InvoiceResponseDto:
    items: list[dict[str, Any]] = []
    for d in inv.details or []:
        items.append(
            {
                "product_id": d.product_id,
                "product_name": d.product_name,
                "quantity": d.quantity,
                "unit_price_snapshot": d.unit_price_snapshot,
                "subtotal_snapshot": (
                    (Decimal(str(d.unit_price_snapshot)) * Decimal(int(d.quantity or 0)))
                    if d.unit_price_snapshot and d.quantity
                    else None
                ),
                "taxes": [
                    {
                        "tax_id": t.tax_id,
                        "rate_snapshot": t.rate_snapshot,
                        "calculated_amount_snapshot": t.calculated_amount_snapshot,
                    }
                    for t in (d.detail_taxes or [])
                ],
            }
        )
    return InvoiceResponseDto(
        id=inv.id,
        invoice_number=inv.invoice_number,
        status=inv.status.value if hasattr(inv.status, "value") else str(inv.status),
        issue_date=inv.issue_date.isoformat() if inv.issue_date else None,
        client_id=inv.client_id,
        client_name_snapshot=inv.client_name_snapshot,
        seller_id=inv.user_id,
        seller_name_snapshot=inv.seller_name_snapshot,
        subtotal_snapshot=inv.subtotal_snapshot,
        tax_total_snapshot=inv.tax_total_snapshot,
        total_snapshot=inv.total_snapshot,
        rejection_reason=inv.rejection_reason,
        items=items,
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateInvoiceCommand:
    dto: CreateInvoiceDto
    seller_id: int


class CreateInvoiceHandler:
    def __init__(
        self,
        invoices: IInvoiceRepository,
        products: IProductRepository,
        clients: IClientRepository,
        users: IUserRepository,
        taxes: ITaxRepository,
    ) -> None:
        self._invoices = invoices
        self._products = products
        self._clients = clients
        self._users = users
        self._taxes = taxes

    async def handle(self, cmd: CreateInvoiceCommand) -> int:
        async with uow() as session:
            invoices = self._invoices.__class__(session)
            products = self._products.__class__(session)
            clients = self._clients.__class__(session)
            users = self._users.__class__(session)
            taxes_repo = self._taxes.__class__(session)

            # 1) Validate unique product in items (req 3).
            seen: set[int] = set()
            for it in cmd.dto.items:
                if it.product_id in seen:
                    raise BusinessError(
                        f"Producto {it.product_id} duplicado en la factura",
                        details={"product_id": it.product_id},
                    )
                seen.add(it.product_id)

            # 2) Resolve products + taxes for each line.
            from app.infrastructure.db.models.invoice import Invoice
            from app.infrastructure.db.models.invoice_detail import InvoiceDetail
            from app.infrastructure.db.models.invoice_detail_tax import InvoiceDetailTax

            line_specs: list[dict[str, Any]] = []
            subtotal = Decimal("0.00")
            tax_total = Decimal("0.00")

            for it in cmd.dto.items:
                product = await products.find_by_id(it.product_id)
                if product is None:
                    raise NotFoundError(f"Producto {it.product_id} no existe")
                if not product.is_active:
                    raise BusinessError(
                        f"Producto {it.product_id} no está activo",
                        details={"product_id": it.product_id},
                    )
                if (product.stock or 0) < it.quantity:
                    raise BusinessError(
                        f"Stock insuficiente para producto {it.product_id}",
                        details={
                            "product_id": it.product_id,
                            "stock": product.stock,
                            "requested": it.quantity,
                        },
                    )
                unit_price = product.price or Decimal("0")
                line_subtotal = _q(unit_price * Decimal(it.quantity))
                subtotal = _q(subtotal + line_subtotal)

                # Resolve taxes for this line.
                chosen_tax_ids = (
                    it.tax_ids
                    if it.tax_ids
                    else [pt.tax_id for pt in (product.product_taxes or [])]
                )
                line_taxes: list[dict[str, Any]] = []
                for tax_id in chosen_tax_ids:
                    tax = await taxes_repo.find_by_id(tax_id)
                    if tax is None:
                        raise NotFoundError(f"Impuesto {tax_id} no existe")
                    rate = tax.current_rate or Decimal("0")
                    line_tax_amount = _q(line_subtotal * rate / Decimal("100"))
                    tax_total = _q(tax_total + line_tax_amount)
                    line_taxes.append(
                        {
                            "tax_id": tax_id,
                            "rate_snapshot": rate,
                            "calculated_amount_snapshot": line_tax_amount,
                        }
                    )

                line_specs.append(
                    {
                        "product": product,
                        "quantity": it.quantity,
                        "unit_price": unit_price,
                        "subtotal": line_subtotal,
                        "taxes": line_taxes,
                    }
                )

            # 3) Resolve client + seller snapshots.
            client_name = client_email = None
            if cmd.dto.client_id is not None:
                c = await clients.find_by_id(cmd.dto.client_id)
                if c is None:
                    raise NotFoundError(f"Cliente {cmd.dto.client_id} no existe")
                client_name = (
                    f"{(c.first_name or '').strip()} {(c.last_name or '').strip()}".strip() or None
                )
                client_email = c.email

            seller = await users.find_by_id(cmd.seller_id)
            if seller is None:
                raise NotFoundError(f"Vendedor {cmd.seller_id} no existe")
            seller_name = (
                f"{(seller.name or '').strip()} {(seller.last_name or '').strip()}".strip()
            )

            # 4) Build the invoice in PENDING_VALIDATION. The validator will
            #    later flip it to VALIDATED; only then do we deduct stock.
            invoice_number = await invoices.next_invoice_number()
            from app.domain.value_objects.payment_method import PaymentMethod

            invoice = Invoice(
                client_id=cmd.dto.client_id,
                subtotal_snapshot=subtotal,
                tax_total_snapshot=tax_total,
                total_snapshot=_q(subtotal + tax_total),
                invoice_number=invoice_number,
                status=InvoiceStatus.PENDING_VALIDATION,
                user_id=cmd.seller_id,
                payment_method=PaymentMethod.CASH,
                client_name_snapshot=client_name,
                client_email_snapshot=client_email,
                seller_name_snapshot=seller_name,
            )
            invoice = await invoices.create(invoice)

            for spec in line_specs:
                detail = InvoiceDetail(
                    invoice_id=invoice.id,
                    product_id=spec["product"].id,
                    product_name=spec["product"].name,
                    quantity=spec["quantity"],
                    unit_price_snapshot=spec["unit_price"],
                )
                session.add(detail)
                await session.flush()
                for tx in spec["taxes"]:
                    session.add(
                        InvoiceDetailTax(
                            detail_id=detail.id,
                            tax_id=tx["tax_id"],
                            rate_snapshot=tx["rate_snapshot"],
                            calculated_amount_snapshot=tx["calculated_amount_snapshot"],
                        )
                    )
            await session.flush()

            # 5) Publish `invoice.created` for the validator.
            from app.infrastructure.messaging.publishers import publish_event

            channel = None
            try:
                from app.infrastructure.messaging.rabbit import get_channel_pool

                # Use a fresh channel; the publisher does not need confirmation.
                channel = await get_channel_pool(get_settings_for_publisher())
                payload = {
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "seller_id": invoice.user_id,
                    "seller_username": seller.username,
                    "client_id": invoice.client_id,
                    "client_name": client_name,
                    "items": [
                        {
                            "product_id": s["product"].id,
                            "product_name": s["product"].name,
                            "quantity": s["quantity"],
                            "unit_price_snapshot": str(s["unit_price"]),
                            "subtotal_snapshot": str(s["subtotal"]),
                        }
                        for s in line_specs
                    ],
                    "subtotal_snapshot": str(subtotal),
                    "tax_total_snapshot": str(tax_total),
                    "total_snapshot": str(_q(subtotal + tax_total)),
                    "taxes": [
                        {
                            "tax_id": t["tax_id"],
                            "rate_snapshot": str(t["rate_snapshot"]),
                        }
                        for s in line_specs
                        for t in s["taxes"]
                    ],
                }
                await publish_event(channel, "invoice.created", payload)
            except Exception:
                # Broker not reachable: keep the invoice; rely on operator
                # retry via the outbox-style recovery script. Logged at app
                # level by the publisher.
                pass
            finally:
                if channel is not None:
                    with contextlib.suppress(Exception):
                        await channel.close()

            return invoice.id


def get_settings_for_publisher():
    from app.config import get_settings

    return get_settings().rabbitmq_url


@dataclass(frozen=True, slots=True)
class UpdateInvoiceCommand:
    invoice_id: int
    dto: UpdateInvoiceDto


class UpdateInvoiceHandler:
    def __init__(
        self,
        invoices: IInvoiceRepository,
        products: IProductRepository,
        clients: IClientRepository,
    ) -> None:
        self._invoices = invoices
        self._products = products
        self._clients = clients

    async def handle(self, cmd: UpdateInvoiceCommand) -> InvoiceResponseDto:
        async with uow() as session:
            invoices = self._invoices.__class__(session)
            products = self._products.__class__(session)
            inv = await invoices.find_by_id(cmd.invoice_id)
            if inv is None:
                raise NotFoundError(f"Factura {cmd.invoice_id} no existe")
            if not can_transition(inv.status, InvoiceStatus.PENDING_VALIDATION):
                raise BusinessError(
                    f"Solo facturas en DRAFT pueden editarse (actual: {inv.status})"
                )
            if cmd.dto.client_id is not None:
                inv.client_id = cmd.dto.client_id
            if cmd.dto.items is not None:
                # Replace details wholesale (snapshot fields re-computed).
                from app.infrastructure.db.models.invoice_detail import InvoiceDetail
                from app.infrastructure.db.models.invoice_detail_tax import InvoiceDetailTax

                await session.flush()
                inv.details.clear()
                await session.flush()
                subtotal = Decimal("0.00")
                tax_total = Decimal("0.00")
                for it in cmd.dto.items:
                    product = await products.find_by_id(it.product_id)
                    if product is None:
                        raise NotFoundError(f"Producto {it.product_id} no existe")
                    line_subtotal = _q((product.price or Decimal("0")) * Decimal(it.quantity))
                    subtotal = _q(subtotal + line_subtotal)
                    detail = InvoiceDetail(
                        invoice_id=inv.id,
                        product_id=product.id,
                        product_name=product.name,
                        quantity=it.quantity,
                        unit_price_snapshot=product.price,
                    )
                    session.add(detail)
                    await session.flush()
                    for tax_id in it.tax_ids:
                        from app.infrastructure.db.models.tax import Tax

                        tax = await session.get(Tax, tax_id)
                        if tax is None:
                            raise NotFoundError(f"Impuesto {tax_id} no existe")
                        line_tax_amount = _q(
                            line_subtotal * (tax.current_rate or Decimal("0")) / Decimal("100")
                        )
                        tax_total = _q(tax_total + line_tax_amount)
                        session.add(
                            InvoiceDetailTax(
                                detail_id=detail.id,
                                tax_id=tax.id,
                                rate_snapshot=tax.current_rate,
                                calculated_amount_snapshot=line_tax_amount,
                            )
                        )
                inv.subtotal_snapshot = subtotal
                inv.tax_total_snapshot = tax_total
                inv.total_snapshot = _q(subtotal + tax_total)
            await session.flush()
            return _to_dto(inv)


@dataclass(frozen=True, slots=True)
class ChangeInvoiceStatusCommand:
    invoice_id: int
    dto: ChangeInvoiceStatusDto
    actor_id: int


class ChangeInvoiceStatusHandler:
    def __init__(
        self,
        invoices: IInvoiceRepository,
        products: IProductRepository,
        stock_movements: IStockMovementRepository,
    ) -> None:
        self._invoices = invoices
        self._products = products
        self._stock_movements = stock_movements

    async def handle(self, cmd: ChangeInvoiceStatusCommand) -> InvoiceResponseDto:
        async with uow() as session:
            invoices = self._invoices.__class__(session)
            products = self._products.__class__(session)
            moves = self._stock_movements.__class__(session)
            inv = await invoices.find_by_id(cmd.invoice_id)
            if inv is None:
                raise NotFoundError(f"Factura {cmd.invoice_id} no existe")
            try:
                target = InvoiceStatus(cmd.dto.status.upper())
            except ValueError as exc:
                raise BusinessError(f"Estado inválido: {cmd.dto.status}") from exc
            if not can_transition(inv.status, target):
                raise BusinessError(f"Transición no permitida: {inv.status} -> {target}")
            # Cancellation restores stock.
            if target == InvoiceStatus.CANCELLED:
                for d in inv.details or []:
                    if d.product_id is None or not d.quantity:
                        continue
                    p = await products.find_by_id(d.product_id)
                    if p is None:
                        continue
                    previous = int(p.stock or 0)
                    p.stock = previous + int(d.quantity)
                    p.version = (p.version or 0) + 1
                    await session.flush()
                    from app.infrastructure.db.models.stock_movement import StockMovement

                    await moves.create(
                        StockMovement(
                            product_id=p.id,
                            type=MovementType.ENTRY,
                            quantity=int(d.quantity),
                            previous_stock=previous,
                            new_stock=int(p.stock or 0),
                            user_id=cmd.actor_id,
                            reference=f"invoice:{inv.id}:cancel",
                        )
                    )
            inv = await invoices.update_status(
                cmd.invoice_id,
                target,
                rejection_reason=cmd.dto.reason,
            )
            return _to_dto(inv)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GetInvoicesQuery:
    page: Page
    search: str | None = None
    status: InvoiceStatus | None = None
    seller_id: int | None = None


class GetInvoicesHandler:
    def __init__(self, invoices: IInvoiceRepository) -> None:
        self._invoices = invoices

    async def handle(self, cmd: GetInvoicesQuery) -> tuple[list[InvoiceResponseDto], int]:
        async with uow() as session:
            invoices = self._invoices.__class__(session)
            rows, total = await invoices.find_all(cmd.page, cmd.search, cmd.status, cmd.seller_id)
            return [_to_dto(r) for r in rows], total


@dataclass(frozen=True, slots=True)
class GetInvoiceQuery:
    invoice_id: int


class GetInvoiceHandler:
    def __init__(self, invoices: IInvoiceRepository) -> None:
        self._invoices = invoices

    async def handle(self, cmd: GetInvoiceQuery) -> InvoiceResponseDto:
        async with uow() as session:
            invoices = self._invoices.__class__(session)
            inv = await invoices.find_by_id(cmd.invoice_id)
            if inv is None:
                raise NotFoundError(f"Factura {cmd.invoice_id} no existe")
            return _to_dto(inv)


@dataclass(frozen=True, slots=True)
class GetInvoiceByNumberQuery:
    invoice_number: str


class GetInvoiceByNumberHandler:
    def __init__(self, invoices: IInvoiceRepository) -> None:
        self._invoices = invoices

    async def handle(self, cmd: GetInvoiceByNumberQuery) -> InvoiceResponseDto:
        async with uow() as session:
            invoices = self._invoices.__class__(session)
            inv = await invoices.find_by_number(cmd.invoice_number)
            if inv is None:
                raise NotFoundError(f"Factura {cmd.invoice_number} no existe")
            return _to_dto(inv)
