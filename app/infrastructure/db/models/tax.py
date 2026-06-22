"""Tax model."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.invoice_detail_tax import InvoiceDetailTax
    from app.infrastructure.db.models.product_tax import ProductTax


class Tax(Base):
    __tablename__ = "taxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    current_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    product_taxes: Mapped[list[ProductTax]] = relationship(
        "ProductTax", back_populates="tax", lazy="noload", cascade="all, delete-orphan"
    )
    detail_taxes: Mapped[list[InvoiceDetailTax]] = relationship(
        "InvoiceDetailTax", back_populates="tax", lazy="noload"
    )
