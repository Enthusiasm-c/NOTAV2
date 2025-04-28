from __future__ import annotations

from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Product(Base):
    """Товар, учётная карточка."""

    # ─── PK ────────────────────────────────────────────────────────────────
    id: Mapped[IntPK]  # type: ignore[valid-type]

    # ─── Атрибуты товара ──────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)  # кг, л, шт …
    default_price: Mapped[float | None] = mapped_column(Numeric(14, 2))  # опционально

    # ─── Связи ─────────────────────────────────────────────────────────────
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        "ProductNameLookup",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.id}: {self.name!r}>"
