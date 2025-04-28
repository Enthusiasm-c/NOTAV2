from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Invoice(Base, IntPK):
    __tablename__ = "invoices"

    # ↓ именно Python-тип 'date', а тип столбца задаём через mapped_column(Date)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    total_sum: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    # --- relationships ------------------------------------------------------ #
    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ----------------------------------------------------------------------- #
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice {self.id} {self.date}>"
