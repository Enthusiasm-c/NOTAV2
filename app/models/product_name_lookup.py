"""
Модель-«словарь» для сопоставления «как товар назван в накладной
→ какой Product в базе».

* product_id  – правильный товар
* alias       – строка, которая распознана в накладной
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK
from .product import Product


class ProductNameLookup(Base, IntPK):
    __tablename__ = "product_name_lookup"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # «как написано в накладной»
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # связи
    product: Mapped["Product"] = relationship(back_populates="name_lookups")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProductNameLookup {self.alias!r} → {self.product_id}>"
