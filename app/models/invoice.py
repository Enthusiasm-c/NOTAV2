from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK

__all__ = ["Invoice"]


class Invoice(Base, IntPK):
    __tablename__ = "invoices"

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    number: Mapped[str | None]
    date: Mapped[date]

    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
