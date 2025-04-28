from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Product(Base, IntPK):
    """Товар из номенклатуры"""

    __tablename__ = "products"

    # основной «человеческий» заголовок
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # базовая единица учёта (кг, л, pack …)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)

    # справочная цена (может быть NULL, если не нужна)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    # ─── связи ───────────────────────────────────────────────────────────────────
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        "ProductNameLookup",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    invoice_items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="product",
    )

    # ─── сервисное ───────────────────────────────────────────────────────────────
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.id}: {self.name!r}>"
