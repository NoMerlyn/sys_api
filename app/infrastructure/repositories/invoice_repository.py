"""SqlInvoiceRepository — full implementation lands in L4.

This stub keeps the package importable and lets L4 add the smart-search
query, the optimistic-locking update, and the next-invoice-number generator
without churning the public interface.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.interfaces.invoice_repository import IInvoiceRepository
from app.core.pagination import Page
from app.domain.value_objects.invoice_status import InvoiceStatus
from app.infrastructure.db.models.invoice import Invoice
from app.infrastructure.db.models.invoice import InvoiceStatus as DbInvoiceStatus


class SqlInvoiceRepository(IInvoiceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, invoice_id: int, *, include_details: bool = True) -> Invoice | None:
        result = await self._session.execute(select(Invoice).where(Invoice.id == invoice_id))
        return result.scalar_one_or_none()

    async def find_by_number(
        self, invoice_number: str, *, include_details: bool = True
    ) -> Invoice | None:
        result = await self._session.execute(
            select(Invoice).where(Invoice.invoice_number == invoice_number)
        )
        return result.scalar_one_or_none()

    async def find_all(
        self,
        page: Page,
        search: str | None = None,
        status: InvoiceStatus | None = None,
        seller_id: int | None = None,
    ) -> tuple[Sequence[Invoice], int]:
        stmt = select(Invoice)
        count_stmt = select(func.count()).select_from(Invoice)
        if search:
            pattern = f"%{search}%"
            filt = or_(
                Invoice.invoice_number.ilike(pattern),
                Invoice.client_name_snapshot.ilike(pattern),
                Invoice.seller_name_snapshot.ilike(pattern),
            )
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        if status is not None:
            stmt = stmt.where(Invoice.status == status)
            count_stmt = count_stmt.where(Invoice.status == status)
        if seller_id is not None:
            stmt = stmt.where(Invoice.user_id == seller_id)
            count_stmt = count_stmt.where(Invoice.user_id == seller_id)
        stmt = stmt.order_by(Invoice.id.desc()).offset(page.offset).limit(page.limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), int(total)

    async def create(self, invoice: Invoice) -> Invoice:
        self._session.add(invoice)
        await self._session.flush()
        return invoice

    async def update_status(
        self,
        invoice_id: int,
        new_status: InvoiceStatus,
        *,
        rejection_reason: str | None = None,
        expected_version: int | None = None,
    ) -> Invoice:
        invoice = await self.find_by_id(invoice_id)
        if invoice is None:
            raise LookupError(f"Invoice {invoice_id} not found")
        if expected_version is not None and invoice.version != expected_version:
            raise RuntimeError("Optimistic lock conflict")
        invoice.status = cast(DbInvoiceStatus, new_status)
        if rejection_reason is not None:
            invoice.rejection_reason = rejection_reason
        invoice.version = (invoice.version or 0) + 1
        await self._session.flush()
        return invoice

    async def next_invoice_number(self) -> str:
        # Simple sequential generator: max numeric suffix + 1. L4 can replace
        # with a transactional sequence if concurrency requires it.
        result = await self._session.execute(
            select(Invoice.invoice_number).order_by(Invoice.id.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "INV-000001"
        try:
            num = int(last.split("-")[-1]) + 1
        except (ValueError, IndexError):
            num = 1
        return f"INV-{num:06d}"
