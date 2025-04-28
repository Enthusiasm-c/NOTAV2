from __future__ import annotations

from decimal import Decimal

from sqlalchemy import DECIMAL, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk


class InvoiceItem(Base):
    """Позиция (строка) накладной."""

    __tablename__ = "invoice_items"

    id: Mapped[IntPK]
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )

    # распознанные данные
    name: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(12, 3))
    unit: Mapped[str] = mapped_column(String(16))
    price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2))
    sum: Mapped[Decimal] = mapped_column(DECIMAL(14, 2))

    # связи ------------------------------------------------------------
    product: Mapped["Product | None"] = relationship(
        "Product", back_populates="items", lazy="joined"
    )
    invoice: Mapped["Invoice"] = relationship(
        "Invoice", back_populates="items", lazy="selectin"
    )
