# app/models/invoice_item.py
"""
Строка накладной (InvoiceItem)
──────────────────────────────
* FK на Invoice и Product
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sum: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ──────────── связи ────────────
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoices.id"), nullable=False
    )
    invoice: Mapped["Invoice"] = relationship(
        "Invoice", back_populates="items"
    )

    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=True
    )
    product: Mapped["Product | None"] = relationship(
        "Product", back_populates="invoice_items"
    )

    # ─────────── удобство ───────────
    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<InvoiceItem id={self.id} name={self.name!r} "
            f"qty={self.quantity} unit={self.unit}>"
        )
