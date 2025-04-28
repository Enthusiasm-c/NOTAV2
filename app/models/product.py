from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK

__all__ = ["Product"]


class Product(Base, IntPK):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)

    # псевдонимы названий
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.id}: {self.name!r} ({self.unit})>"
