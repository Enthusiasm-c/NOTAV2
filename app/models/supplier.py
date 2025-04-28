# app/models/supplier.py
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk


class Supplier(Base):
    """Поставщик-контрагент."""

    __tablename__ = "suppliers"

    # PK
    id: Mapped[int_pk]

    # «человеческое» название (уникально)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # внутренний код из учётной системы (опционально, но тоже уникально)
    code: Mapped[str | None] = mapped_column(String(64), unique=True)

    # связанные накладные
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # псевдонимы названий (lookup'и)
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # удобное представление
    def __repr__(self) -> str:  # pragma: no cover
        ident = self.code or self.id
        return f"<Supplier {ident}: {self.name!r}>"
