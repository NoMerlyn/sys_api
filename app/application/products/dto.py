"""Products Pydantic DTOs."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class CreateProductDto(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    price: Decimal = Field(ge=0)
    stock: int = Field(ge=0)
    is_active: bool = True


class UpdateProductDto(BaseModel):
    name: str | None = Field(default=None, max_length=20)
    price: Decimal | None = Field(default=None, ge=0)
    stock: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductResponseDto(BaseModel):
    id: int
    name: str | None
    price: Decimal | None
    stock: int | None
    is_active: bool
