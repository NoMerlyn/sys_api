"""Clients Pydantic DTOs."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class CreateClientDto(BaseModel):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    cedula: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None


class UpdateClientDto(BaseModel):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    cedula: str | None = Field(default=None, max_length=20)
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
