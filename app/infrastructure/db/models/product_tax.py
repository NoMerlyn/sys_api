"""ProductTax many-to-many join."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

if TYPE_CHECKING:
    from app.infrastructure.db.models.product import Product
    from app.infrastructure.db.models.tax import Tax


class ProductTax(Base):
    __tablename__ = "product_taxes"
    __table_args__ = (
        Index("ix_product_taxes_product_id", "product_id"),
        Index("ix_product_taxes_tax_id", "tax_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    tax_id: Mapped[int] = mapped_column(ForeignKey("taxes.id", ondelete="CASCADE"), nullable=False)

    product: Mapped[Product] = relationship(
        "Product", back_populates="product_taxes", lazy="joined"
    )
    tax: Mapped[Tax] = relationship("Tax", back_populates="product_taxes", lazy="joined")
