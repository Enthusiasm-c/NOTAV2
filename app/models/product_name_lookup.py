"""
Модель-«словарь» для сопоставления «как товар назван в накладной
→ какой Product в базе».

* invoice_id  – накладная-источник
* product_id  – правильный товар
* name        – строка из накладной
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK
from .invoice import Invoice
from .product import Product


class InvoiceNameLookup(Base, IntPK):
    __tablename__ = "invoice_name_lookup"

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # «как написано в накладной»
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # связи
    invoice: Mapped["Invoice"] = relationship(back_populates="name_lookups")
    product: Mapped["Product"] = relationship(back_populates="name_lookups")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InvoiceNameLookup {self.name!r} → {self.product_id} in {self.invoice_id}>"
