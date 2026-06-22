"""SQLAlchemy declarative base and common mixins.

`TableNameMixin` was removed: explicit `__tablename__` declarations are
clearer and dodge a class-attribute quirk that confuses static analyzers.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds `created_at` (immutable) and `updated_at` (auto-updated)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds `is_active` and a `soft_delete()` helper.

    Soft delete is a domain action, not a cascade. Repositories expose
    `soft_delete_by_id()` and the entity itself offers `soft_delete()`.
    """

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def soft_delete(self) -> None:
        self.is_active = False
