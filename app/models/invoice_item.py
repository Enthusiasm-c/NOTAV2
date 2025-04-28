# app/models/invoice_item.py
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk


class InvoiceItem(Base):
    """
    Строка накладной
    ─────────────────
    name_raw  – оригинальное название из файла  
    qty/price/total – Decimal(12,2)  
    product_id может быть NULL, пока товар не сматчился
    """

    __tablename__ = "invoice_items"

    id:         Mapped[int_pk]         = mapped_column(primary_key=True)
    invoice_id: Mapped[int]            = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[int | None]     = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    name_raw: Mapped[str]              = mapped_column(String, nullable=False)
    unit:     Mapped[str]              = mapped_column(String(16), nullable=False)

    qty:   Mapped[Decimal]             = mapped_column(Numeric(12, 2), nullable=False)
    price: Mapped[Decimal]             = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal]             = mapped_column(Numeric(12, 2), nullable=False)

    # связи
    invoice: Mapped["Invoice"]         = relationship(back_populates="items")
    product: Mapped["Product"]         = relationship(back_populates="invoice_items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Item {self.name_raw!r} × {self.qty} {self.unit} = {self.total}>"
