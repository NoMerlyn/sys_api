"""Unit tests for the invoice state machine."""

from __future__ import annotations

import pytest

from app.domain.value_objects.invoice_status import (
    InvoiceStatus,
    allowed_next,
    can_transition,
)


def test_draft_can_go_to_pending_validation() -> None:
    assert can_transition(InvoiceStatus.DRAFT, InvoiceStatus.PENDING_VALIDATION)
    assert InvoiceStatus.PENDING_VALIDATION in allowed_next(InvoiceStatus.DRAFT)


def test_pending_validation_can_split() -> None:
    assert can_transition(InvoiceStatus.PENDING_VALIDATION, InvoiceStatus.VALIDATED)
    assert can_transition(InvoiceStatus.PENDING_VALIDATION, InvoiceStatus.REJECTED)


def test_validated_to_confirmed() -> None:
    assert can_transition(InvoiceStatus.VALIDATED, InvoiceStatus.CONFIRMED)


def test_confirmed_to_cancelled() -> None:
    assert can_transition(InvoiceStatus.CONFIRMED, InvoiceStatus.CANCELLED)


@pytest.mark.parametrize(
    "src,dst",
    [
        (InvoiceStatus.DRAFT, InvoiceStatus.CONFIRMED),
        (InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED),
        (InvoiceStatus.PENDING_VALIDATION, InvoiceStatus.CONFIRMED),
        (InvoiceStatus.PENDING_VALIDATION, InvoiceStatus.CANCELLED),
        (InvoiceStatus.REJECTED, InvoiceStatus.CONFIRMED),
        (InvoiceStatus.REJECTED, InvoiceStatus.PENDING_VALIDATION),
        (InvoiceStatus.CANCELLED, InvoiceStatus.CONFIRMED),
        (InvoiceStatus.VALIDATED, InvoiceStatus.CANCELLED),
        (InvoiceStatus.VALIDATED, InvoiceStatus.DRAFT),
    ],
)
def test_forbidden_transitions(src: InvoiceStatus, dst: InvoiceStatus) -> None:
    assert not can_transition(src, dst)


def test_rejected_is_terminal() -> None:
    assert allowed_next(InvoiceStatus.REJECTED) == frozenset()


def test_cancelled_is_terminal() -> None:
    assert allowed_next(InvoiceStatus.CANCELLED) == frozenset()
