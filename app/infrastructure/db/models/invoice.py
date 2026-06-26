"""Invoice model.

Status enum is extended vs Proyecto_A:
  DRAFT, PENDING_VALIDATION, VALIDATED, REJECTED, CONFIRMED, CANCELLED.
Transitions are enforced in the application layer via `InvoiceStatus`.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.client import Client
    from app.infrastructure.db.models.invoice_detail import InvoiceDetail
    from app.infrastructure.db.models.user import User


class InvoiceStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentMethod(enum.StrEnum):
    CASH = "CASH"


class Invoice(Base, SoftDeleteMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_client_id", "client_id"),
        Index("ix_invoices_user_id", "user_id"),
        Index("ix_invoices_issue_date", "issue_date"),
        Index("ix_invoices_invoice_number", "invoice_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True
    )
    issue_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    subtotal_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_total_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.PENDING_VALIDATION,
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"),
        default=PaymentMethod.CASH,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    client_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_email_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_cedula_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    client_phone_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_address_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clave_acceso_snapshot: Mapped[str | None] = mapped_column(String(49), nullable=True)
    sri_xml_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    client: Mapped[Client | None] = relationship("Client", back_populates="invoices", lazy="noload")
    user: Mapped[User | None] = relationship("User", back_populates="invoices", lazy="joined")
    details: Mapped[list[InvoiceDetail]] = relationship(
        "InvoiceDetail", back_populates="invoice", lazy="selectin", cascade="all, delete-orphan"
    )
    parent: Mapped[Invoice | None] = relationship(
        "Invoice", remote_side="Invoice.id", backref="revisions", lazy="noload"
    )
