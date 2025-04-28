from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Product(Base, IntPK):
    __tablename__ = "products"

    # «человеческое» имя
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # единица учёта (kg, l, pcs …)
    unit: Mapped[str] = mapped_column(String(16))

    # базовая цена (может быть null)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    # связанные таблицы
    invoice_items: Mapped[list["InvoiceItem"]] = relationship(back_populates="product")
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.id}: {self.name}>"
