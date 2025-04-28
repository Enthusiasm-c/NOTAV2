from __future__ import annotations
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class InvoiceItem(Base, IntPK):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    sum: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    # --- relationships ------------------------------------------------------ #
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="invoice_items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Item inv={self.invoice_id} prod={self.product_id}>"
