"""Money value object: Decimal with 2-dp rounding, non-negative."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class Money:
    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, "value", Decimal(str(self.value)))
        if self.value < 0:
            raise ValueError("El valor monetario no puede ser negativo.")
        rounded = self.value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "value", rounded)

    def add(self, other: Money) -> Money:
        return Money(self.value + other.value)

    def multiply(self, factor: int | Decimal) -> Money:
        return Money(self.value * Decimal(str(factor)))

    def equals(self, other: object) -> bool:
        return isinstance(other, Money) and self.value == other.value

    def __str__(self) -> str:
        return f"{self.value:.2f}"
