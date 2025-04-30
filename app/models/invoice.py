"""
Invoice model for Nota V2.

This module defines the Invoice model which represents invoices in the database.
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import IntPK
from .supplier import Supplier

if TYPE_CHECKING:
    from .invoice_item import InvoiceItem

class Invoice(IntPK):
    """
    Invoice model representing invoices in the database.
    
    Attributes:
        id (int): Primary key
        number (Optional[str]): Invoice number
        date (datetime): Invoice date
        supplier_id (int): Foreign key to supplier
        supplier (Supplier): Related supplier
        items (List[InvoiceItem]): List of invoice items
        comment (Optional[str]): Additional notes
    """
    __tablename__ = "invoices"
    
    number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    supplier: Mapped[Supplier] = relationship(Supplier, backref="invoices")
    items: Mapped[List["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan"
    )
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    def __str__(self) -> str:
        """Return string representation of the invoice."""
        return f"Накладная {self.number or 'б/н'} от {self.date.strftime('%d.%m.%Y')}"
