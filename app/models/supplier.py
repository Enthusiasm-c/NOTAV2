from __future__ import annotations

from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

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
