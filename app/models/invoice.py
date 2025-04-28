# app/models/invoice.py
"""
Накладная (Invoice)
───────────────────
* один-ко-многим с InvoiceItem
"""

from __future__ import annotations

from datetime import date
from sqlalchemy import Column, Integer, Date, String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str | None] = mapped_column(String, nullable=True)
    issued_at: Mapped[date] = mapped_column(Date, nullable=False)

    supplier: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer: Mapped[str | None] = mapped_column(String, nullable=True)
    total_sum: Mapped[float | None] = mapped_column(nullable=True)

    # ─────────────── связи ───────────────
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ───────────── удобство ──────────────
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice id={self.id} №{self.number} {self.issued_at}>"
