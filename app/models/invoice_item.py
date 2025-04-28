from __future__ import annotations

from sqlalchemy import Numeric, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class InvoiceItem(Base):
    """Строка накладной."""

    # ─── PK ────────────────────────────────────────────────────────────────
    id: Mapped[IntPK]  # type: ignore[valid-type]

    # ─── FK на накладную и товар ──────────────────────────────────────────
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="items")

    # ─── Кол-во, цена ─────────────────────────────────────────────────────
    quantity: Mapped[float] = mapped_column(Numeric(12, 3))
    price: Mapped[float] = mapped_column(Numeric(14, 2))
    sum: Mapped[float] = mapped_column(Numeric(14, 2))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InvoiceItem {self.id}: {self.quantity} × {self.product_id}>"
