from sqlalchemy import Column, Integer, String, Date, Numeric, Enum
from app.db import Base
from enum import Enum as PyEnum

class InvoiceStatus(PyEnum):
    pending = "pending"
    confirming = "confirming"
    confirmed = "confirmed"
    exported = "exported"

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier = Column(String(255))
    buyer = Column(String(255))
    date = Column(Date)
    total_sum = Column(Numeric)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.pending)
