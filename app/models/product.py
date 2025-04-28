# app/models/product.py
"""
Основная номенклатура товаров.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .base import Base, int_pk


class Product(Base):
    __tablename__ = "products"

    # ───── поля ──────────────────────────────────────────────────────
    id: Mapped[int] = int_pk()
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)  # кг, л, шт …

    # ───── связи ────────────────────────────────────────────────────
    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    # новые lookups (alias’ы)
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product #{self.id} {self.name}>"
