"""Unit tests for the Money value object."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.value_objects.money import Money


def test_positive_creation() -> None:
    m = Money(Decimal("10.50"))
    assert m.value == Decimal("10.50")


def test_negative_rejected() -> None:
    with pytest.raises(ValueError):
        Money(Decimal("-0.01"))


def test_rounding_to_two_decimals() -> None:
    assert Money(Decimal("10.555")).value == Decimal("10.56")
    assert Money(Decimal("10.554")).value == Decimal("10.55")


def test_arithmetic() -> None:
    a = Money(Decimal("10.25"))
    b = Money(Decimal("5.75"))
    assert a.add(b).value == Decimal("16.00")
    assert a.multiply(3).value == Decimal("30.75")


def test_equality() -> None:
    assert Money(Decimal("10.50")).equals(Money(Decimal("10.50")))
    assert not Money(Decimal("10.50")).equals(Money(Decimal("11")))
