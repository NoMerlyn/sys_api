"""InvoiceDetail model (line item with snapshot fields)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.invoice import Invoice
    from app.infrastructure.db.models.invoice_detail_tax import InvoiceDetailTax
    from app.infrastructure.db.models.product import Product


class InvoiceDetail(Base):
    __tablename__ = "invoice_details"
    __table_args__ = (
        Index("ix_invoice_details_invoice_id", "invoice_id"),
        Index("ix_invoice_details_product_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    invoice: Mapped[Invoice | None] = relationship(
        "Invoice", back_populates="details", lazy="joined"
    )
    product: Mapped[Product | None] = relationship(
        "Product", back_populates="invoice_details", lazy="noload"
    )
    detail_taxes: Mapped[list[InvoiceDetailTax]] = relationship(
        "InvoiceDetailTax",
        back_populates="invoice_detail",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
