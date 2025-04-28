from __future__ import annotations

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[IntPK]

    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL")
    )

    number: Mapped[str | None] = mapped_column(String(64))
    date: Mapped[Date]
    total_sum: Mapped[Numeric(14, 2)]

    supplier: Mapped["Supplier"] | None = relationship(
        "Supplier",
        back_populates="invoices",
        lazy="joined",
    )
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
