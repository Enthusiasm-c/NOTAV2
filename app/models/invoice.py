from __future__ import annotations

from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[IntPK]

    # FK → suppliers.id
    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_date: Mapped[date | None] = mapped_column(Date)

    supplier: Mapped["Supplier"] = relationship(
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

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice {self.id} supplier={self.supplier_id}>"
