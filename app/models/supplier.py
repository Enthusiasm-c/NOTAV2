from __future__ import annotations

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Supplier(Base):
    """Поставщик товаров."""

    # ─── PK ────────────────────────────────────────────────────────────────
    id: Mapped[IntPK]  # type: ignore[valid-type]

    # ─── Данные поставщика ────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), unique=True)

    # ─── Связи ─────────────────────────────────────────────────────────────
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="supplier",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier {self.code or self.id}: {self.name!r}>"
