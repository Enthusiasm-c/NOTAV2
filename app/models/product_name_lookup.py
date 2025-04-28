from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk


class ProductNameLookup(Base):
    """
    Таблица с псевдонимами (синонимами) товаров ―
    используется для «мягкого» сопоставления названий из накладных.
    """

    __tablename__ = "product_name_lookup"

    id: Mapped[IntPK]
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(128), index=True)

    # связь к Product
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="name_lookups",
        lazy="joined",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lookup {self.alias!r} → {self.product_id}>"
