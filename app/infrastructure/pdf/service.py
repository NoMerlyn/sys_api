"""PdfService — invoice PDF generation with ReportLab.

Output mirrors the current pdfkit layout in Proyecto_A/pos-api:
  - Title centered, invoice number top-right.
  - Seller + client block (left).
  - Issue date + status badge top-right.
  - Line items table (product, qty, unit price, subtotal).
  - Tax breakdown if any.
  - Subtotal, tax, total aligned right.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _fmt_money(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


class PdfService:
    def render_invoice(self, invoice: Any) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=f"Factura {invoice.invoice_number or invoice.id}",
        )
        styles = getSampleStyleSheet()
        h1 = styles["Title"]
        small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9)
        bold = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold")

        story: list[Any] = []
        story.append(Paragraph(f"Factura {invoice.invoice_number or invoice.id}", h1))
        story.append(Spacer(1, 4 * mm))

        # Header table: client + seller + dates
        client_label = invoice.client_name_snapshot or "Consumidor final"
        seller_label = invoice.seller_name_snapshot or "Sistema"
        issued = (
            invoice.issue_date.strftime("%Y-%m-%d %H:%M")
            if isinstance(invoice.issue_date, datetime)
            else "-"
        )
        header = Table(
            [
                ["Cliente:", client_label, "Fecha:", issued],
                ["Vendedor:", seller_label, "Estado:", str(invoice.status)],
            ],
            colWidths=[28 * mm, 80 * mm, 28 * mm, 30 * mm],
        )
        header.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                    ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(header)
        story.append(Spacer(1, 6 * mm))

        # Items table
        rows: list[list[str]] = [
            ["Producto", "Cant.", "Precio", "Subtotal"],
        ]
        for d in invoice.details or []:
            rows.append(
                [
                    d.product_name or "-",
                    str(d.quantity or 0),
                    _fmt_money(d.unit_price_snapshot),
                    _fmt_money(
                        (float(d.unit_price_snapshot or 0) * int(d.quantity or 0))
                        if d.unit_price_snapshot
                        else None
                    ),
                ]
            )
        items_table = Table(
            rows,
            colWidths=[90 * mm, 18 * mm, 28 * mm, 30 * mm],
            repeatRows=1,
        )
        items_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(items_table)
        story.append(Spacer(1, 6 * mm))

        # Totals block
        totals_rows = [
            ["Subtotal", _fmt_money(invoice.subtotal_snapshot)],
            ["IVA", _fmt_money(invoice.tax_total_snapshot)],
            ["Total", _fmt_money(invoice.total_snapshot)],
        ]
        totals = Table(
            totals_rows,
            colWidths=[140 * mm, 26 * mm],
            hAlign="RIGHT",
        )
        totals.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                    ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 11),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#111827")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(totals)

        if invoice.rejection_reason:
            story.append(Spacer(1, 6 * mm))
            story.append(
                Paragraph(
                    f"<b>Motivo de rechazo:</b> {invoice.rejection_reason}",
                    small,
                )
            )

        doc.build(story)
        return buf.getvalue()
