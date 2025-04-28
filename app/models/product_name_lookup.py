from __future__ import annotations

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class ProductNameLookup(Base):
    """
    «Словарь» альтернативных названий товара, чтобы находить
    позиции счёта-фактуры по разным написаниям.

    • `name`        – вариант написания, уникален  
    • `product_id`  – FK → products.id (ON DELETE CASCADE)  
    """

    __tablename__ = "product_name_lookup"

    id: Mapped[int] = IntPK
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # ───── связи ────────────────────────────────────────────────────────────
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="name_lookups",
    )

    # ───── вспомогательные методы ──────────────────────────────────────────
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lookup {self.name!r} → {self.product_id}>"
