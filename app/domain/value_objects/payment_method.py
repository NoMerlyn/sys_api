"""Payment method enum (only CASH in v1, kept for extensibility)."""

from __future__ import annotations

import enum


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
