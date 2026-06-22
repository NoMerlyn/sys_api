"""Products router (admin manages, sellers can list for-sale)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.application.common.uow import uow
from app.application.products import (
    CreateProductCommand,
    CreateProductDto,
    CreateProductHandler,
    DeleteProductCommand,
    DeleteProductHandler,
    GetProductHandler,
    GetProductQuery,
    ListProductsForSaleHandler,
    ListProductsForSaleQuery,
    ListProductsHandler,
    ListProductsQuery,
    ProductResponseDto,
    UpdateProductCommand,
    UpdateProductDto,
    UpdateProductHandler,
)
from app.core.pagination import parse_page
from app.presentation.deps import CurrentUserDep, require_role

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=dict)
async def list_products(
    _: CurrentUserDep,
    page: int | None = Query(default=None),
    limit: int | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository

        handler = ListProductsHandler(SqlProductRepository(session))
        rows, total = await handler.handle(
            ListProductsQuery(page=parse_page(page, limit), search=search)
        )
    return {"data": [r.model_dump(mode="json") for r in rows], "total": total}


@router.get("/for-sale", response_model=dict)
async def list_products_for_sale(
    _: CurrentUserDep,
    page: int | None = Query(default=None),
    limit: int | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository

        handler = ListProductsForSaleHandler(SqlProductRepository(session))
        rows, total = await handler.handle(
            ListProductsForSaleQuery(page=parse_page(page, limit), search=search)
        )
    return {"data": [r.model_dump(mode="json") for r in rows], "total": total}


@router.get("/{product_id}", response_model=ProductResponseDto)
async def get_product(_: CurrentUserDep, product_id: int) -> ProductResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository

        handler = GetProductHandler(SqlProductRepository(session))
        return await handler.handle(GetProductQuery(product_id=product_id))


@router.post(
    "",
    response_model=ProductResponseDto,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def create_product(_: CurrentUserDep, payload: CreateProductDto) -> ProductResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository

        create_h = CreateProductHandler(SqlProductRepository(session))
        product_id = await create_h.handle(CreateProductCommand(dto=payload))
        get_h = GetProductHandler(SqlProductRepository(session))
        return await get_h.handle(GetProductQuery(product_id=product_id))


@router.put(
    "/{product_id}",
    response_model=ProductResponseDto,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def update_product(
    _: CurrentUserDep, product_id: int, payload: UpdateProductDto
) -> ProductResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository

        handler = UpdateProductHandler(SqlProductRepository(session))
        return await handler.handle(UpdateProductCommand(product_id=product_id, dto=payload))


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def delete_product(_: CurrentUserDep, product_id: int) -> None:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository

        handler = DeleteProductHandler(SqlProductRepository(session))
        await handler.handle(DeleteProductCommand(product_id=product_id))
