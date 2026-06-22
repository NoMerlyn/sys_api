"""InvoiceDetailTax model (per-line tax snapshot)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.invoice_detail import InvoiceDetail
    from app.infrastructure.db.models.tax import Tax


class InvoiceDetailTax(Base):
    __tablename__ = "invoice_detail_taxes"
    __table_args__ = (
        Index("ix_invoice_detail_taxes_detail_id", "detail_id"),
        Index("ix_invoice_detail_taxes_tax_id", "tax_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detail_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice_details.id", ondelete="CASCADE"), nullable=True
    )
    tax_id: Mapped[int | None] = mapped_column(
        ForeignKey("taxes.id", ondelete="SET NULL"), nullable=True
    )
    rate_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    calculated_amount_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    invoice_detail: Mapped[InvoiceDetail | None] = relationship(
        "InvoiceDetail", back_populates="detail_taxes", lazy="joined"
    )
    tax: Mapped[Tax | None] = relationship("Tax", back_populates="detail_taxes", lazy="joined")
