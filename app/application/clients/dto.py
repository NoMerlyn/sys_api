"""Clients Pydantic DTOs."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domain.value_objects.cedula import Cedula


class _CedulaMixin(BaseModel):
    cedula: str | None = Field(default=None, max_length=20)

    @field_validator("cedula")
    @classmethod
    def _validate_cedula(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        # Strip whitespace; tolerate "1712345678 " or "171234567-8" etc.
        cleaned = value.strip().replace(" ", "").replace("-", "")
        Cedula(cleaned)  # raises BusinessException on failure
        return cleaned


class CreateClientDto(_CedulaMixin):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None


class UpdateClientDto(_CedulaMixin):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_active: bool | None = None


class ClientResponseDto(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    cedula: str | None
    phone: str | None
    address: str | None
    email: str | None
    is_active: bool
