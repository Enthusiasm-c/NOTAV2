from __future__ import annotations

from datetime import date

from sqlalchemy import String, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Invoice(Base):
    """Оприходованная накладная."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[str | None] = mapped_column(String(64))
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    supplier: Mapped[str | None] = mapped_column(String(255))

    # --- relationships -------------------------------------------------
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice {self.id} №{self.number or '-'}>"
