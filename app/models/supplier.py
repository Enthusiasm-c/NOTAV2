from __future__ import annotations

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # связь «поставщик → его накладные»
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="supplier",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier {self.id}: {self.name!r}>"
