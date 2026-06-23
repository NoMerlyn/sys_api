"""Pagination helpers shared by routers and queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")

DEFAULT_PAGE = 1
DEFAULT_LIMIT = 10
MAX_LIMIT = 100


@dataclass(frozen=True, slots=True)
class Page:
    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


@dataclass(frozen=True, slots=True)
class PaginatedResponse:
    data: list[Any]
    page: int
    limit: int
    total: int


def parse_page(page: int | None, limit: int | None) -> Page:
    safe_page = max(DEFAULT_PAGE, int(page or DEFAULT_PAGE))
    safe_limit = min(MAX_LIMIT, max(1, int(limit or DEFAULT_LIMIT)))
    return Page(page=safe_page, limit=safe_limit)
