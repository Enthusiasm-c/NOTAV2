from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Invoice(Base):
    """Накладная."""

    # ─── PK ────────────────────────────────────────────────────────────────
    id: Mapped[IntPK]  # type: ignore[valid-type]

    # ─── Метаданные ───────────────────────────────────────────────────────
    number: Mapped[str | None] = mapped_column(unique=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # ─── FK на поставщика ────────────────────────────────────────────────
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="invoices")

    # ─── Финансы ──────────────────────────────────────────────────────────
    total_sum: Mapped[float] = mapped_column(Numeric(14, 2))

    # ─── Позиции ──────────────────────────────────────────────────────────
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice {self.number or self.id} от {self.date}>"
