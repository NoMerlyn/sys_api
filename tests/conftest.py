"""Test fixtures (kept minimal for the L2 checkpoint; L3+ add per-test fixtures)."""

from __future__ import annotations

import pytest

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (  # noqa: F401 — register tables
    BlockedUser,
    Client,
    ErrorLog,
    Invoice,
    InvoiceDetail,
    InvoiceDetailTax,
    ProcessedEvent,
    Product,
    ProductTax,
    Role,
    StockMovement,
    Tax,
    User,
    UserRole,
)


@pytest.fixture(scope="session")
def base():
    return Base


@pytest.fixture(autouse=True)
def _ensure_models_imported():
    """Import every model so `Base.metadata` is fully populated before tests run."""
    yield
