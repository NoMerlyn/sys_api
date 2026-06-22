"""Email value object."""

from __future__ import annotations

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email

from app.core.exceptions import BusinessException


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        try:
            validated = validate_email(self.value, check_deliverability=False)
        except EmailNotValidError as exc:
            raise BusinessException(
                f"Correo inválido: {self.value}", details={"field": "email"}
            ) from exc
        # Normalize to lowercase, ASCII form.
        object.__setattr__(self, "value", validated.normalized.lower())

    def __str__(self) -> str:
        return self.value
