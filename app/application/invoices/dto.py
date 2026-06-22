"""Invoices Pydantic DTOs."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class CreateInvoiceItemDto(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    # Optional tax_ids to apply per line. If omitted, we use the product's
    # default tax set (ProductTax rows). Empty list = no tax on that line.
    tax_ids: list[int] = Field(default_factory=list)


class CreateInvoiceDto(BaseModel):
    client_id: int | None = None
    items: list[CreateInvoiceItemDto] = Field(min_length=1)
    # If provided, server recalculates; if omitted, server computes from
    # current product prices + tax rates. The frontend always omits to avoid
    # tampering.
    subtotal: Decimal | None = None
    tax_total: Decimal | None = None
    total: Decimal | None = None


class UpdateInvoiceItemDto(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    tax_ids: list[int] = Field(default_factory=list)


class UpdateInvoiceDto(BaseModel):
    client_id: int | None = None
    items: list[UpdateInvoiceItemDto] | None = None


class ChangeInvoiceStatusDto(BaseModel):
    status: str  # only CANCELLED is accepted from this endpoint
    reason: str | None = None


class InvoiceItemResponseDto(BaseModel):
    product_id: int | None
    product_name: str | None
    quantity: int | None
    unit_price_snapshot: Decimal | None
    subtotal_snapshot: Decimal | None
    taxes: list[InvoiceItemTaxDto] = Field(default_factory=list)


class InvoiceItemTaxDto(BaseModel):
    tax_id: int | None
    rate_snapshot: Decimal | None
    calculated_amount_snapshot: Decimal | None


class InvoiceResponseDto(BaseModel):
    id: int
    invoice_number: str | None
    status: str
    issue_date: str | None
    client_id: int | None
    client_name_snapshot: str | None
    seller_id: int | None
    seller_name_snapshot: str | None
    subtotal_snapshot: Decimal | None
    tax_total_snapshot: Decimal | None
    total_snapshot: Decimal | None
    rejection_reason: str | None
    items: list[InvoiceItemResponseDto] = Field(default_factory=list)
