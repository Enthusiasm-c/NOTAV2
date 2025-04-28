from __future__ import annotations

from datetime import date

from sqlalchemy import Column, Date, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class Invoice(Base):
    """Покупатель ⇄ Поставщик + список строк (InvoiceItem)."""

    __tablename__ = "invoices"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    supplier_name: str | None = Column(String, nullable=True)
    buyer_name: str | None = Column(String, nullable=True)
    date: date | None = Column(Date, default=date.today, nullable=True)

    raw_text: str | None = Column(Text, nullable=True)      # полный OCR-текст
    status: str = Column(String, default="pending")         # pending / sent / error …

    # ――― related objects ―――
    items = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
