"""Products use cases."""

from app.application.products.dto import (
    CreateProductDto,
    ProductResponseDto,
    UpdateProductDto,
)
from app.application.products.handlers import (
    CreateProductCommand,
    CreateProductHandler,
    DeleteProductCommand,
    DeleteProductHandler,
    GetProductHandler,
    GetProductQuery,
    ListProductsForSaleHandler,
    ListProductsForSaleQuery,
    ListProductsHandler,
    ListProductsQuery,
    UpdateProductCommand,
    UpdateProductHandler,
)

__all__ = [
    "CreateProductCommand",
    "CreateProductDto",
    "CreateProductHandler",
    "DeleteProductCommand",
    "DeleteProductHandler",
    "GetProductHandler",
    "GetProductQuery",
    "ListProductsForSaleHandler",
    "ListProductsForSaleQuery",
    "ListProductsHandler",
    "ListProductsQuery",
    "ProductResponseDto",
    "UpdateProductCommand",
    "UpdateProductDto",
    "UpdateProductHandler",
]
