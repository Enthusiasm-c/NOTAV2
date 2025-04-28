from __future__ import annotations
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    # составной первичный ключ
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price:    Mapped[Decimal] = mapped_column(Numeric(14, 2))
    sum:      Mapped[Decimal] = mapped_column(Numeric(14, 2))

    # --- relationships ------------------------------------------------------ #
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="invoice_items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Item inv={self.invoice_id} prod={self.product_id}>"
