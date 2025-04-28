# app/models/product.py
"""
Модель Product
──────────────
* основная номенклатура товара;
* связь «один-ко-многим» с InvoiceItem (строки накладных);
* связь «один-ко-многим» с ProductNameLookup – таблицей всех
  «альтернативных» названий, найденных fuzzy-алгоритмом.
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # — связи -------------------------------------------------------------
    invoice_items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        "ProductNameLookup",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # — удобство отображения ---------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product id={self.id} name={self.name!r}>"
