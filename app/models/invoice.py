# app/models/invoice.py
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk, str_pk


class Invoice(Base):
    """
    Накладная (шапка документа)
    ───────────────────────────
    * supplier_id → ссыл­ка на постав­щика  
    * doc_date    → дата накладной  
    * doc_number  → номер (если есть; может быть NULL)
    """
    __tablename__ = "invoices"

    id: Mapped[int_pk] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True, nullable=False)

    doc_date:   Mapped[date]    = mapped_column(Date, nullable=False)
    doc_number: Mapped[str_pk]  = mapped_column(String(64), nullable=True, unique=False)

    # обратные связи
    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")
    items:    Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice #{self.doc_number or self.id} {self.doc_date}>"


class InvoiceItem(Base):
    """
    Строка накладной
    ────────────────
    * invoice_id → родительская накладная  
    * product_id → продукт (может быть NULL, если пока не сматчился)  
    * unit       → текстовая единица измерения из накладной  
    * qty, price, total → Decimal(14, 2)
    """
    __tablename__ = "invoice_items"

    id:         Mapped[int_pk] = mapped_column(primary_key=True)
    invoice_id: Mapped[int]    = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True, nullable=True)

    name_raw: Mapped[str] = mapped_column(String, nullable=False)  # оригинальное название из PDF/фото
    unit:     Mapped[str] = mapped_column(String(16), nullable=False)

    qty:   Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # обратные связи
    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="invoice_items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Item {self.name_raw!r} × {self.qty} {self.unit} = {self.total}>"
