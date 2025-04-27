# app/models/product.py
"""
SQLAlchemy-модель Product.

• Содержит базовые сведения о товаре: id, name, unit.  
• Связи:
    – `invoice_items`  ←→  InvoiceItem.product
    – `name_lookups`   ←→  InvoiceNameLookup.product
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Product(Base):
    __tablename__ = "products"

    # ────────────────────────── Колонки ───────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ────────────────────────── Связи ORM ─────────────────────────────
    invoice_items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

    name_lookups: Mapped[list["InvoiceNameLookup"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # ────────────────────────── Dunder’ы ──────────────────────────────
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product id={self.id} name='{self.name}'>"
