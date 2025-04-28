from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class ProductNameLookup(Base, IntPK):
    __tablename__ = "product_name_lookup"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String, index=True)

    # обратная связь к Product
    product: Mapped["Product"] = relationship(back_populates="name_lookups")
