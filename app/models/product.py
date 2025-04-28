from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Product(Base):
    __tablename__ = "products"

    id: Mapped[IntPK]

    # наименование в учётной системе
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), unique=True)

    # 👇 псевдонимы
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
