"""Products use-case handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.common.interfaces.product_repository import IProductRepository
from app.application.common.uow import uow
from app.application.products.dto import (
    CreateProductDto,
    ProductResponseDto,
    UpdateProductDto,
)
from app.core.exceptions import NotFoundError
from app.core.pagination import Page


def _to_dto(p: Any) -> ProductResponseDto:
    return ProductResponseDto(
        id=p.id,
        name=p.name,
        price=p.price,
        stock=p.stock,
        is_active=p.is_active,
    )


@dataclass(frozen=True, slots=True)
class ListProductsQuery:
    page: Page
    search: str | None = None


class ListProductsHandler:
    def __init__(self, products: IProductRepository) -> None:
        self._products = products

    async def handle(self, cmd: ListProductsQuery) -> tuple[list[ProductResponseDto], int]:
        async with uow() as session:
            products = self._products.__class__(session)  # type: ignore[call-arg]
            rows, total = await products.find_all(cmd.page, cmd.search)
            return [_to_dto(p) for p in rows], total


@dataclass(frozen=True, slots=True)
class ListProductsForSaleQuery:
    page: Page
    search: str | None = None


class ListProductsForSaleHandler:
    def __init__(self, products: IProductRepository) -> None:
        self._products = products

    async def handle(self, cmd: ListProductsForSaleQuery) -> tuple[list[ProductResponseDto], int]:
        async with uow() as session:
            products = self._products.__class__(session)  # type: ignore[call-arg]
            rows, total = await products.find_for_sale(cmd.page, cmd.search)
            return [_to_dto(p) for p in rows], total


@dataclass(frozen=True, slots=True)
class GetProductQuery:
    product_id: int


class GetProductHandler:
    def __init__(self, products: IProductRepository) -> None:
        self._products = products

    async def handle(self, cmd: GetProductQuery) -> ProductResponseDto:
        async with uow() as session:
            products = self._products.__class__(session)  # type: ignore[call-arg]
            p = await products.find_by_id(cmd.product_id)
            if p is None:
                raise NotFoundError(f"Producto {cmd.product_id} no encontrado")
            return _to_dto(p)


@dataclass(frozen=True, slots=True)
class CreateProductCommand:
    dto: CreateProductDto


class CreateProductHandler:
    def __init__(self, products: IProductRepository) -> None:
        self._products = products

    async def handle(self, cmd: CreateProductCommand) -> int:
        async with uow() as session:
            products = self._products.__class__(session)  # type: ignore[call-arg]
            from app.infrastructure.db.models.product import Product

            row = Product(
                name=cmd.dto.name,
                price=cmd.dto.price,
                stock=cmd.dto.stock,
                is_active=cmd.dto.is_active,
            )
            row = await products.create(row)
            return row.id


@dataclass(frozen=True, slots=True)
class UpdateProductCommand:
    product_id: int
    dto: UpdateProductDto


class UpdateProductHandler:
    def __init__(self, products: IProductRepository) -> None:
        self._products = products

    async def handle(self, cmd: UpdateProductCommand) -> ProductResponseDto:
        async with uow() as session:
            products = self._products.__class__(session)  # type: ignore[call-arg]
            p = await products.find_by_id(cmd.product_id)
            if p is None:
                raise NotFoundError(f"Producto {cmd.product_id} no encontrado")
            if cmd.dto.name is not None:
                p.name = cmd.dto.name
            if cmd.dto.price is not None:
                p.price = cmd.dto.price
            if cmd.dto.stock is not None:
                p.stock = cmd.dto.stock
            if cmd.dto.is_active is not None:
                p.is_active = cmd.dto.is_active
            await products.update(p)
            return _to_dto(p)


@dataclass(frozen=True, slots=True)
class DeleteProductCommand:
    product_id: int


class DeleteProductHandler:
    def __init__(self, products: IProductRepository) -> None:
        self._products = products

    async def handle(self, cmd: DeleteProductCommand) -> None:
        async with uow() as session:
            products = self._products.__class__(session)  # type: ignore[call-arg]
            await products.soft_delete(cmd.product_id)
