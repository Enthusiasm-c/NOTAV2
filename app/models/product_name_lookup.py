from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class ProductNameLookup(Base):
    __tablename__ = "product_name_lookup"

    id: Mapped[IntPK]

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="name_lookups",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lookup {self.alias!r} → {self.product_id}>"
