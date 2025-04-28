# app/models/supplier.py
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK  # ← импортируем alias первичного ключа


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[IntPK]                           # ← раньше здесь был mapped_column(Integer,…

    # «человеческое» название поставщика
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # код (из вашей учётной системы или отчёта)
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    # связь с накладными
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="supplier",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier {self.code or self.id}: {self.name!r}>"
