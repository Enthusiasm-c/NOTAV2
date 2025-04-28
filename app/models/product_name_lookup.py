# app/models/product_name_lookup.py
"""
Таблица с «псевдонимами» товаров:
* «яблоко», «apple», «apel» → product_id = 42
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk


class ProductNameLookup(Base):
    """Уникальная пара (product_id, alias)."""

    __tablename__ = "product_name_lookup"

    id: Mapped[int] = int_pk()
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    # back-reference в Product.name_lookups
    product: Mapped["Product"] = relationship(back_populates="name_lookups")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lookup {self.alias!r} → {self.product_id}>"
