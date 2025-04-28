# app/models/supplier.py
"""
Supplier model
──────────────
• одна строка в таблице suppliers = один поставщик  
• связь Invoice ←→ Supplier (один-ко-многим)
"""

from __future__ import annotations

from sqlalchemy import String, Integer, Column
from sqlalchemy.orm import relationship

from .base import Base


class Supplier(Base):
    """Поставщик (контрагент)."""

    __tablename__ = "suppliers"

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String(255), unique=True, nullable=False)

    # ← back-populated из Invoice.supplier
    invoices = relationship("Invoice", back_populates="supplier", cascade="all, delete-orphan")

    # удобное строковое представление
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier id={self.id} name={self.name!r}>"
