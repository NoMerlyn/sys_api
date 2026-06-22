"""Product model."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.invoice_detail import InvoiceDetail
    from app.infrastructure.db.models.product_tax import ProductTax
    from app.infrastructure.db.models.stock_movement import StockMovement


class Product(Base, SoftDeleteMixin):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_is_active_stock", "is_active", "stock"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product_taxes: Mapped[list[ProductTax]] = relationship(
        "ProductTax", back_populates="product", lazy="noload", cascade="all, delete-orphan"
    )
    invoice_details: Mapped[list[InvoiceDetail]] = relationship(
        "InvoiceDetail", back_populates="product", lazy="noload"
    )
    stock_movements: Mapped[list[StockMovement]] = relationship(
        "StockMovement", back_populates="product", lazy="noload"
    )
