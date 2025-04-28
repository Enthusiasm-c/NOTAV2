from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class InvoiceNameLookup(Base):
    """
    Таблица «синонимов» — какое имя встретилось в накладной
    и к какому Product мы его привязали вручную.
    """

    __tablename__ = "invoice_name_lookup"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    raw_name: Mapped[str] = mapped_column(String(255), index=True, unique=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )

    # --- relationships -------------------------------------------------
    product: Mapped["Product"] = relationship(back_populates="name_lookups")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lookup «{self.raw_name}» → {self.product_id}>"
