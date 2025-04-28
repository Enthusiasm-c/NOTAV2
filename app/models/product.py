from __future__ import annotations

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # внутренний/артикул
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # базовая единица учёта (kg, l, pcs…)
    uom: Mapped[str | None] = mapped_column(String(16))

    # опционально – фасовка и себестоимость
    pack_qty: Mapped[float | None] = mapped_column(Numeric(12, 4))
    cost: Mapped[float | None] = mapped_column(Numeric(14, 2))

    # псевдонимы, присланные поставщиками
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        "ProductNameLookup",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="product",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.code or self.id}: {self.name!r}>"
