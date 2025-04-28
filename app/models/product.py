from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk


class Product(Base):
    """Единый справочник товаров."""

    __tablename__ = "products"

    id: Mapped[IntPK]
    code: Mapped[str | None] = mapped_column(String(32), unique=True)  # внутренний артикул
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(16))  # кг, л, шт …

    # связи ------------------------------------------------------------
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        "ProductNameLookup",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # удобный repr
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.id}: {self.name}>"
