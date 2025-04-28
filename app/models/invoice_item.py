from __future__ import annotations

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[IntPK]

    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float]
    unit: Mapped[str] = mapped_column(String(16))
    price: Mapped[Numeric(12, 2)]
    sum: Mapped[Numeric(14, 2)]

    product: Mapped["Product"] | None = relationship(
        "Product",
        back_populates="items",
        lazy="joined",
    )
    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="items",
        lazy="selectin",
    )
