__all__ = ["InvoiceItem"]

from sqlalchemy import Column, Integer, ForeignKey, String, Numeric, Float
from .base import Base

class InvoiceItem(Base):
    """Позиция в накладной

    Variables:
        id: int
        invoice_id: int (FK)
        product_id: int (nullable)
        parsed_name: str
        quantity: float
        unit: str
        price: float
        sum: float
        match_confidence: float
    """
    __tablename__ = "invoice_items"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    parsed_name = Column(String(255), nullable=False)
    quantity = Column(Numeric, nullable=False)
    unit = Column(String(32), nullable=True)
    price = Column(Numeric, nullable=True)
    sum = Column(Numeric, nullable=True)
    match_confidence = Column(Float, nullable=True)
