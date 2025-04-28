from __future__ import annotations

from sqlalchemy import ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class InvoiceItem(Base):
    """Позиция в накладной."""

    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )

    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)

    # --- relationships -------------------------------------------------
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship(back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Item inv={self.invoice_id} prod={self.product_id} "
            f"qty={self.quantity} price={self.price}>"
        )
