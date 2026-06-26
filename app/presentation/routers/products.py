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
async def create_product(user: CurrentUserDep, payload: CreateProductDto) -> ProductResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository
        repo = SqlProductRepository(session)
        create_h = CreateProductHandler(repo)
        product_id = await create_h.handle(CreateProductCommand(dto=payload))
        
        # Audit creation
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="CREATE",
                entity="PRODUCT",
                entity_id=product_id,
                user_id=user.id,
                detail=json.dumps(payload.model_dump(), ensure_ascii=False)
            )
            
        get_h = GetProductHandler(repo)
        return await get_h.handle(GetProductQuery(product_id=product_id))


@router.put(
    "/{product_id}",
    response_model=ProductResponseDto,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def update_product(
    user: CurrentUserDep, product_id: int, payload: UpdateProductDto
) -> ProductResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository
        repo = SqlProductRepository(session)
        
        old_prod = await repo.find_by_id(product_id)
        before_state = {}
        if old_prod:
            before_state = {
                "name": old_prod.name,
                "price": float(old_prod.price),
                "stock": old_prod.stock,
            }
            
        handler = UpdateProductHandler(repo)
        res = await handler.handle(UpdateProductCommand(product_id=product_id, dto=payload))
        
        after_state = {
            "name": res.name,
            "price": float(res.price),
            "stock": res.stock,
        }
        
        # Audit update
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="UPDATE",
                entity="PRODUCT",
                entity_id=product_id,
                user_id=user.id,
                detail=json.dumps({
                    "before": before_state,
                    "after": after_state
                }, ensure_ascii=False),
            )
            
        return res


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def delete_product(user: CurrentUserDep, product_id: int) -> None:
    async with uow() as session:
        from app.infrastructure.repositories.product_repository import SqlProductRepository
        repo = SqlProductRepository(session)
        
        handler = DeleteProductHandler(repo)
        await handler.handle(DeleteProductCommand(product_id=product_id))
        
        # Audit deletion
        import json
        from app.application.audit import audit
        async with audit(session) as log:
            await log.add(
                action="STATUS_CHANGE",
                entity="PRODUCT",
                entity_id=product_id,
                user_id=user.id,
                detail=json.dumps({"is_active": False, "deleted": True}, ensure_ascii=False),
            )
