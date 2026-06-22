"""Smoke test: verify all modules can be imported (catches missing imports early)."""

from __future__ import annotations


def test_imports_app_core() -> None:
    import app.config  # noqa: F401
    import app.core.di  # noqa: F401
    import app.core.exceptions  # noqa: F401
    import app.core.pagination  # noqa: F401
    import app.core.security  # noqa: F401


def test_imports_app_domain() -> None:
    import app.domain.value_objects.email  # noqa: F401
    import app.domain.value_objects.invoice_status  # noqa: F401
    import app.domain.value_objects.money  # noqa: F401
    import app.domain.value_objects.movement_type  # noqa: F401
    import app.domain.value_objects.payment_method  # noqa: F401


def test_imports_app_infrastructure_db() -> None:
    import app.infrastructure.db.base  # noqa: F401
    import app.infrastructure.db.models  # noqa: F401
    import app.infrastructure.db.session  # noqa: F401


def test_imports_app_application() -> None:
    import app.application.auth  # noqa: F401
    import app.application.clients  # noqa: F401
    import app.application.common.interfaces  # noqa: F401
    import app.application.common.tokens  # noqa: F401
    import app.application.common.uow  # noqa: F401
    import app.application.invoices  # noqa: F401
    import app.application.products  # noqa: F401
    import app.application.taxes  # noqa: F401
    import app.application.users  # noqa: F401


def test_imports_app_infrastructure() -> None:
    import app.infrastructure.errors.log_writer  # noqa: F401
    import app.infrastructure.messaging.consumer  # noqa: F401
    import app.infrastructure.messaging.publishers  # noqa: F401
    import app.infrastructure.messaging.rabbit  # noqa: F401
    import app.infrastructure.messaging.topology  # noqa: F401
    import app.infrastructure.pdf.service  # noqa: F401
    import app.infrastructure.repositories  # noqa: F401


def test_imports_app_presentation() -> None:
    import app.presentation.deps  # noqa: F401
    import app.presentation.routers.auth  # noqa: F401
    import app.presentation.routers.clients  # noqa: F401
    import app.presentation.routers.invoice_pdf  # noqa: F401
    import app.presentation.routers.invoices  # noqa: F401
    import app.presentation.routers.products  # noqa: F401
    import app.presentation.routers.roles  # noqa: F401
    import app.presentation.routers.taxes  # noqa: F401
    import app.presentation.routers.users  # noqa: F401


def test_value_object_email() -> None:
    from app.domain.value_objects.email import Email

    e = Email("Foo@Example.com")
    assert e.value == "foo@example.com"


def test_value_object_money() -> None:
    from decimal import Decimal

    from app.domain.value_objects.money import Money

    assert Money(Decimal("1.005")).value == Decimal("1.01")


def test_state_machine_draft_to_confirmed_path() -> None:
    from app.domain.value_objects.invoice_status import (
        InvoiceStatus,
        can_transition,
    )

    # The full happy-path through extended states.
    assert can_transition(InvoiceStatus.DRAFT, InvoiceStatus.PENDING_VALIDATION)
    assert can_transition(InvoiceStatus.PENDING_VALIDATION, InvoiceStatus.VALIDATED)
    assert can_transition(InvoiceStatus.VALIDATED, InvoiceStatus.CONFIRMED)
    assert can_transition(InvoiceStatus.CONFIRMED, InvoiceStatus.CANCELLED)


def test_state_machine_rejected_terminal() -> None:
    from app.domain.value_objects.invoice_status import (
        InvoiceStatus,
        can_transition,
    )

    for target in (
        InvoiceStatus.DRAFT,
        InvoiceStatus.PENDING_VALIDATION,
        InvoiceStatus.VALIDATED,
        InvoiceStatus.CONFIRMED,
        InvoiceStatus.CANCELLED,
    ):
        assert not can_transition(InvoiceStatus.REJECTED, target)
