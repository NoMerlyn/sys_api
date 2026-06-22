"""Dependency injection tokens for repositories.

Usage:
    from app.application.common.tokens import TOKENS
    @inject
    def __init__(self, users: Annotated[IUserRepository, FromDishka(TOKENS.USER_REPOSITORY)]):
        ...

The router layer uses FastAPI's `Depends(get_user_repository)` which reads
from the same constants. Keeping one source of truth avoids typos.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepositoryTokens:
    USER_REPOSITORY: str = "user_repository"
    ROLE_REPOSITORY: str = "role_repository"
    BLOCKED_USER_REPOSITORY: str = "blocked_user_repository"
    CLIENT_REPOSITORY: str = "client_repository"
    PRODUCT_REPOSITORY: str = "product_repository"
    TAX_REPOSITORY: str = "tax_repository"
    INVOICE_REPOSITORY: str = "invoice_repository"
    STOCK_MOVEMENT_REPOSITORY: str = "stock_movement_repository"
    ERROR_LOG_REPOSITORY: str = "error_log_repository"
    PROCESSED_EVENT_REPOSITORY: str = "processed_event_repository"


TOKENS = RepositoryTokens()
