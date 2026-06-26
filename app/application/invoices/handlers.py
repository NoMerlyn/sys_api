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


class _TaxSpec:
    """Duck-typed tax object for build_sri_xml."""
    def __init__(self, rate_snapshot: Decimal, calculated_amount_snapshot: Decimal) -> None:
        self.rate_snapshot = rate_snapshot
        self.calculated_amount_snapshot = calculated_amount_snapshot


class _DetailSpec:
    """Duck-typed detail object for build_sri_xml."""
    def __init__(self, product_id: int | None, product_name: str | None, quantity: int,
                 unit_price_snapshot: Decimal, taxes: list) -> None:
        self.product_id = product_id
        self.product_name = product_name
        self.quantity = quantity
        self.unit_price_snapshot = unit_price_snapshot
        self.detail_taxes = taxes


def _specs_to_details(line_specs: list) -> list:
    """Convert line_specs (CreateInvoiceHandler internal data) to duck-typed detail objects."""
    result = []
    for s in line_specs:
        taxes = [_TaxSpec(t["rate_snapshot"], t["calculated_amount_snapshot"]) for t in s["taxes"]]
        result.append(_DetailSpec(
            product_id=s["product"].id,
            product_name=s["product"].name,
            quantity=s["quantity"],
            unit_price_snapshot=s["unit_price"],
            taxes=taxes,
        ))
    return result


def _to_dto(inv: Any) -> InvoiceResponseDto:
    items: list = []  # populated as InvoiceItemResponseDto below
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
        client_cedula_snapshot=inv.client_cedula_snapshot,
        client_phone_snapshot=inv.client_phone_snapshot,
        client_address_snapshot=inv.client_address_snapshot,
        seller_id=inv.user_id,
        seller_name_snapshot=inv.seller_name_snapshot,
        subtotal_snapshot=inv.subtotal_snapshot,
        tax_total_snapshot=inv.tax_total_snapshot,
        total_snapshot=inv.total_snapshot,
        rejection_reason=inv.rejection_reason,
        clave_acceso_snapshot=inv.clave_acceso_snapshot,
        sri_xml_snapshot=inv.sri_xml_snapshot,
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
            invoices = self._invoices.__class__(session)  # type: ignore[call-arg]
            products = self._products.__class__(session)  # type: ignore[call-arg]
            clients = self._clients.__class__(session)  # type: ignore[call-arg]
            users = self._users.__class__(session)  # type: ignore[call-arg]
            taxes_repo = self._taxes.__class__(session)  # type: ignore[call-arg]

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
            client_name = client_email = client_cedula = client_phone = client_address = None
            if cmd.dto.client_id is not None:
                c = await clients.find_by_id(cmd.dto.client_id)
                if c is None:
                    raise NotFoundError(f"Cliente {cmd.dto.client_id} no existe")
                client_name = (
                    f"{(c.first_name or '').strip()} {(c.last_name or '').strip()}".strip() or None
                )
                client_email = c.email
                client_cedula = c.cedula
                client_phone = c.phone
                client_address = c.address
            else:
                client_name = "CONSUMIDOR FINAL"
                client_cedula = "9999999999999"
                client_address = "N/A"

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
                client_cedula_snapshot=client_cedula,
                client_phone_snapshot=client_phone,
                client_address_snapshot=client_address,
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

            # Generate Access Key and SRI XML Snapshot
            from datetime import datetime

            from app.config import get_settings
            from app.core.sri import build_sri_xml, generate_access_key

            settings = get_settings()
            issue_date = invoice.issue_date or datetime.now()
            date_str = issue_date.strftime("%d%m%Y")
            seq_number = "000000001"
            if invoice.invoice_number:
                digits = "".join(char for char in invoice.invoice_number if char.isdigit())
                if digits:
                    seq_number = f"{int(digits):09d}"

            access_key = generate_access_key(
                date_str=date_str,
                cod_doc="01",
                ruc=settings.merchant_ruc,
                environment="1" if settings.env == "dev" else "2",
                establishment="001",
                emission_point="001",
                sequential=seq_number
            )
            invoice.clave_acceso_snapshot = access_key

            # Get client safely
            client_obj = None
            if cmd.dto.client_id is not None:
                client_obj = await clients.find_by_id(cmd.dto.client_id)

            xml_str = build_sri_xml(invoice, client_obj, settings, preloaded_details=_specs_to_details(line_specs))
            invoice.sri_xml_snapshot = xml_str
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

            # Auto-confirm after 2 seconds (demo mode).
            import asyncio as _asyncio
            invoice_id_for_confirm = invoice.id
            _asyncio.get_event_loop().call_later(
                2.0,
                lambda: _asyncio.ensure_future(_auto_confirm_invoice(invoice_id_for_confirm))
            )

            return invoice.id


def get_settings_for_publisher():
    from app.config import get_settings

    return get_settings().rabbitmq_url


async def _auto_confirm_invoice(invoice_id: int) -> None:
    """Background task: confirm invoice after a short delay (demo mode)."""
    import asyncio
    await asyncio.sleep(0)  # yield once so the task runs cleanly
    try:
        from app.application.common.uow import uow
        from app.infrastructure.repositories.invoice_repository import SqlInvoiceRepository
        async with uow() as session:
            repo = SqlInvoiceRepository(session)
            inv = await repo.find_by_id(invoice_id)
            if inv is not None and inv.status == InvoiceStatus.PENDING_VALIDATION:
                await repo.update_status(invoice_id, InvoiceStatus.CONFIRMED)
    except Exception:
        pass


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
            invoices = self._invoices.__class__(session)  # type: ignore[call-arg]
            products = self._products.__class__(session)  # type: ignore[call-arg]
            inv = await invoices.find_by_id(cmd.invoice_id)
            if inv is None:
                raise NotFoundError(f"Factura {cmd.invoice_id} no existe")
            if not can_transition(inv.status, InvoiceStatus.PENDING_VALIDATION):
                raise BusinessError(
                    f"Solo facturas en DRAFT pueden editarse (actual: {inv.status})"
                )
            if cmd.dto.client_id is not None:
                inv.client_id = cmd.dto.client_id
                clients_repo = self._clients.__class__(session)  # type: ignore[call-arg]
                c = await clients_repo.find_by_id(cmd.dto.client_id)
                if c is None:
                    raise NotFoundError(f"Cliente {cmd.dto.client_id} no existe")
                inv.client_name_snapshot = (
                    f"{(c.first_name or '').strip()} {(c.last_name or '').strip()}".strip() or None
                )
                inv.client_email_snapshot = c.email
                inv.client_cedula_snapshot = c.cedula
                inv.client_phone_snapshot = c.phone
                inv.client_address_snapshot = c.address
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

            # Re-generate clave_acceso and sri_xml
            from datetime import datetime

            from app.config import get_settings
            from app.core.sri import build_sri_xml, generate_access_key

            settings = get_settings()
            issue_date = inv.issue_date or datetime.now()
            date_str = issue_date.strftime("%d%m%Y")
            seq_number = "000000001"
            if inv.invoice_number:
                digits = "".join(char for char in inv.invoice_number if char.isdigit())
                if digits:
                    seq_number = f"{int(digits):09d}"

            access_key = generate_access_key(
                date_str=date_str,
                cod_doc="01",
                ruc=settings.merchant_ruc,
                environment="1" if settings.env == "dev" else "2",
                establishment="001",
                emission_point="001",
                sequential=seq_number
            )
            inv.clave_acceso_snapshot = access_key

            client_obj = None
            if inv.client_id is not None:
                clients_repo = self._clients.__class__(session)  # type: ignore[call-arg]
                client_obj = await clients_repo.find_by_id(inv.client_id)

            xml_str = build_sri_xml(inv, client_obj, settings)
            inv.sri_xml_snapshot = xml_str
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
            invoices = self._invoices.__class__(session)  # type: ignore[call-arg]
            products = self._products.__class__(session)  # type: ignore[call-arg]
            moves = self._stock_movements.__class__(session)  # type: ignore[call-arg]
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
                import json as _json

                from app.infrastructure.db.models.audit_log import AuditLog
                from app.infrastructure.db.models.stock_movement import StockMovement

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
                    session.add(
                        AuditLog(
                            action="STOCK_CHANGE",
                            entity="Product",
                            entity_id=p.id,
                            user_id=cmd.actor_id,
                            detail=_json.dumps(
                                {
                                    "motivo": "anulacion_factura",
                                    "factura_id": inv.id,
                                    "producto": p.name,
                                    "cantidad_restituida": int(d.quantity),
                                    "before": {"stock": previous},
                                    "after": {"stock": int(p.stock or 0)},
                                },
                                ensure_ascii=False,
                            ),
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
            invoices = self._invoices.__class__(session)  # type: ignore[call-arg]
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
            invoices = self._invoices.__class__(session)  # type: ignore[call-arg]
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
            invoices = self._invoices.__class__(session)  # type: ignore[call-arg]
            inv = await invoices.find_by_number(cmd.invoice_number)
            if inv is None:
                raise NotFoundError(f"Factura {cmd.invoice_number} no existe")
            return _to_dto(inv)
