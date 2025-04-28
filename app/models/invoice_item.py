from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base


class InvoiceItem(Base):
    """Строка накладной (связь с Product по fuzzy-match, если найден)."""

    __tablename__ = "invoice_items"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id: int = Column(
        Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    product_id: int | None = Column(Integer, ForeignKey("products.id"), nullable=True)

    parsed_name: str = Column(String, nullable=False)   # как увидел OCR/парсер
    quantity = Column(Numeric)                          # количество
    unit: str | None = Column(String)                   # л / кг / шт …
    price = Column(Numeric)                             # цена за единицу
    sum = Column(Numeric)                               # итог по строке
    match_confidence = Column(Numeric)                  # 0‒1 от fuzzy-match

    # ――― relationships ―――
    product = relationship("Product", back_populates="items", lazy="joined")
    invoice = relationship("Invoice", back_populates="items", lazy="joined")
