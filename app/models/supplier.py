from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK

__all__ = ["Supplier"]


class Supplier(Base, IntPK):
    __tablename__ = "suppliers"

    # «человеческое» название
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # опциональный код из учётной системы
    code: Mapped[str | None] = mapped_column(String(64), unique=True)

    # связь «1-N» с накладными
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier {self.code or self.id}: {self.name!r}>"
