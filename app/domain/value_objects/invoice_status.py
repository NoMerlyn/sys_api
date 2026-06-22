"""Invoice status enum + transition table.

The state machine lives here so every layer (router, handler, broker consumer)
asks the same source whether a transition is legal.

Allowed transitions:
    DRAFT              -> PENDING_VALIDATION
    PENDING_VALIDATION -> VALIDATED | REJECTED
    VALIDATED          -> CONFIRMED
    CONFIRMED          -> CANCELLED
"""

from __future__ import annotations

import enum


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


_ALLOWED: dict[InvoiceStatus, frozenset[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: frozenset({InvoiceStatus.PENDING_VALIDATION}),
    InvoiceStatus.PENDING_VALIDATION: frozenset({InvoiceStatus.VALIDATED, InvoiceStatus.REJECTED}),
    InvoiceStatus.VALIDATED: frozenset({InvoiceStatus.CONFIRMED}),
    InvoiceStatus.REJECTED: frozenset(),
    InvoiceStatus.CONFIRMED: frozenset({InvoiceStatus.CANCELLED}),
    InvoiceStatus.CANCELLED: frozenset(),
}


def can_transition(src: InvoiceStatus, dst: InvoiceStatus) -> bool:
    return dst in _ALLOWED.get(src, frozenset())


def allowed_next(src: InvoiceStatus) -> frozenset[InvoiceStatus]:
    return _ALLOWED.get(src, frozenset())
