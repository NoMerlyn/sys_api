"""PDF router (mounted under /invoices by main.py)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.application.common.uow import uow
from app.application.invoices import (
    GetInvoiceByNumberHandler,
    GetInvoiceByNumberQuery,
    GetInvoiceHandler,
    GetInvoiceQuery,
)
from app.infrastructure.pdf.service import PdfService
from app.presentation.deps import CurrentUserDep

router = APIRouter(prefix="/invoices", tags=["invoices-pdf"])


@router.get("/{invoice_id}/pdf", response_class=Response)
async def invoice_pdf(user: CurrentUserDep, invoice_id: int) -> Response:
    async with uow() as session:
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )

        handler = GetInvoiceHandler(SqlInvoiceRepository(session))
        invoice = await handler.handle(GetInvoiceQuery(invoice_id=invoice_id))
    if "ADMINISTRATOR" not in user.roles and invoice.seller_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    pdf_bytes = PdfService().render_invoice(invoice)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="factura_{invoice.invoice_number or invoice.id}.pdf"'
            )
        },
    )


@router.get("/by-number/{invoice_number}/pdf", response_class=Response)
async def invoice_pdf_by_number(user: CurrentUserDep, invoice_number: str) -> Response:
    async with uow() as session:
        from app.infrastructure.repositories.invoice_repository import (
            SqlInvoiceRepository,
        )

        handler = GetInvoiceByNumberHandler(SqlInvoiceRepository(session))
        invoice = await handler.handle(GetInvoiceByNumberQuery(invoice_number=invoice_number))
    if "ADMINISTRATOR" not in user.roles and invoice.seller_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    pdf_bytes = PdfService().render_invoice(invoice)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": (f'inline; filename="factura_{invoice_number}.pdf"')},
    )
