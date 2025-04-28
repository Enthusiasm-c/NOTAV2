from __future__ import annotations

from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Product(Base):
    """Номенклатура товаров (справочник)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    unit: Mapped[str | None] = mapped_column(String(32))
    default_price: Mapped[float | None] = mapped_column(Float)

    # --- relationships -------------------------------------------------
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    name_lookups: Mapped[list["InvoiceNameLookup"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    # human-friendly repr
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.id} «{self.name}»>"
