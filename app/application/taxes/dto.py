"""Taxes Pydantic DTOs."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class CreateTaxDto(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    current_rate: Decimal = Field(ge=0, le=100)


class UpdateTaxDto(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    current_rate: Decimal | None = Field(default=None, ge=0, le=100)


class TaxResponseDto(BaseModel):
    id: int
    name: str | None
    current_rate: Decimal | None
