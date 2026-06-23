"""Cedula (Ecuadorian national ID) value object.

Validation: módulo 10 algorithm.

A valid Ecuadorian cédula has 10 digits, where:
- The first two indicate the province (01-24) or "30" for foreigners.
- The last digit is the verifier (computed via módulo 10).
- The verifier is computed by:
  1. Multiplying each of the first 9 digits by the alternating
     coefficients [2, 1, 2, 1, 2, 1, 2, 1, 2] (left to right).
  2. If a product is > 9, subtract 9.
  3. Sum all the resulting values.
  4. The verifier is (10 - (sum % 10)) % 10.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import BusinessException

# Coefficients applied to the first 9 digits, left to right.
_COEFFICIENTS: tuple[int, ...] = (2, 1, 2, 1, 2, 1, 2, 1, 2)

# Province codes (first two digits). "30" is reserved for foreigners
# and is not officially emitted, but several legacy systems accept it.
_PROVINCE_CODES: set[str] = {f"{i:02d}" for i in range(1, 25)} | {"30"}


def _is_valid_cedula(value: str) -> bool:
    if not value or len(value) != 10 or not value.isdigit():
        return False
    if value[:2] not in _PROVINCE_CODES:
        return False
    if value == "0000000000":
        return False
    digits = [int(c) for c in value]
    # First 9 digits are the body; 10th is the verifier.
    total = 0
    for digit, coef in zip(digits[:9], _COEFFICIENTS):
        product = digit * coef
        if product > 9:
            product -= 9
        total += product
    verifier = (10 - (total % 10)) % 10
    return verifier == digits[9]


@dataclass(frozen=True, slots=True)
class Cedula:
    value: str

    def __post_init__(self) -> None:
        if not _is_valid_cedula(self.value):
            raise BusinessException(
                f"Cédula inválida: {self.value!r}",
                details={"field": "cedula"},
            )

    def __str__(self) -> str:
        return self.value


__all__ = ["Cedula"]
