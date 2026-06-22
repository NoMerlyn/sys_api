"""IInvoiceRepository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.pagination import Page
from app.domain.value_objects.invoice_status import InvoiceStatus


class IInvoiceRepository(ABC):
    @abstractmethod
    async def find_by_id(
        self, invoice_id: int, *, include_details: bool = True
    ) -> object | None: ...

    @abstractmethod
    async def find_by_number(
        self, invoice_number: str, *, include_details: bool = True
    ) -> object | None: ...

    @abstractmethod
    async def find_all(
        self,
        page: Page,
        search: str | None = None,
        status: InvoiceStatus | None = None,
        seller_id: int | None = None,
    ) -> tuple[Sequence[object], int]: ...

    @abstractmethod
    async def create(self, invoice: object) -> object: ...

    @abstractmethod
    async def update_status(
        self,
        invoice_id: int,
        new_status: InvoiceStatus,
        *,
        rejection_reason: str | None = None,
        expected_version: int | None = None,
    ) -> object: ...

    @abstractmethod
    async def next_invoice_number(self) -> str: ...
