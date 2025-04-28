from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK
from .supplier import Supplier


class Invoice(Base, IntPK):
    __tablename__ = "invoices"

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")

    number: Mapped[str | None] = mapped_column(String(64), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    total_sum: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    # дочерние строки
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice #{self.number} {self.date} supplier={self.supplier_id}>"
