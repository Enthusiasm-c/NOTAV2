# app/models/product_name_lookup.py
"""
Таблица альтернативных (ранее встречавшихся) имён товара.
Используется fuzzy-поиском для повышения точности распознавания.
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class ProductNameLookup(Base):
    __tablename__ = "product_name_lookups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    product: Mapped["Product"] = relationship(
        "Product", back_populates="name_lookups"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProductNameLookup id={self.id} name={self.name!r} "
            f"confidence={self.confidence:.2f}>"
        )
