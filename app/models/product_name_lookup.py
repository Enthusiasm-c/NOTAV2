from __future__ import annotations

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK

__all__ = ["ProductNameLookup"]


class ProductNameLookup(Base, IntPK):
    __tablename__ = "product_name_lookup"

    # сам «псевдоним»
    alias: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # FK на основной товар
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    product: Mapped["Product"] = relationship(back_populates="name_lookups")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lookup {self.alias!r} → {self.product_id}>"
