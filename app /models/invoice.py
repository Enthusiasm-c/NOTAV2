__all__ = ["Invoice", "InvoiceNameLookup"]

from sqlalchemy import Column, Integer, String, Date, Text, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from .base import Base
import enum

class InvoiceStatusEnum(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    exported = "exported"

class Invoice(Base):
    """Invoice (накладная)

    Variables:
        id: int
        supplier_name: str
        buyer_name: str
        date: date
        raw_text: str
        status: str (Enum)
    """
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    supplier_name = Column(String(255))
    buyer_name = Column(String(255))
    date = Column(Date)
    raw_text = Column(Text)
    status = Column(Enum(InvoiceStatusEnum), default=InvoiceStatusEnum.pending)

class InvoiceNameLookup(Base):
    """Запоминает сопоставления parsed_name -> FK Product

    Variables:
        id: int
        parsed_name: str
        product_id: int (FK)
    """
    __tablename__ = "invoice_name_lookup"
    id = Column(Integer, primary_key=True)
    parsed_name = Column(String(255), nullable=False, unique=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime(), server_default=func.now())
