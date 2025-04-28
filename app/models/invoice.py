# app/models/invoice.py
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, int_pk


class Invoice(Base):
    """Заголовок накладной."""

    __tablename__ = "invoices"

    id:        Mapped[int_pk] = mapped_column(primary_key=True)
    number:    Mapped[str | None] = mapped_column(String(64), index=True)
    date:      Mapped[date]       = mapped_column(nullable=False)

    # foreign keys
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # суммы
    total_sum: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # --- relationships ------------------------------------------------------
    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")
    items:    Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice {self.number or self.id} – {self.date}>"
