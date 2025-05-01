"""
Invoice model for Nota V2.

This module defines the Invoice model which represents invoices in the database.
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Integer, String, ForeignKey, Date, Numeric, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import IntPK

if TYPE_CHECKING:
    from .supplier import Supplier
    from .invoice_item import InvoiceItem

class Invoice(IntPK):
    """
    Invoice model representing invoices in the database.
    
    Attributes:
        id (int): Primary key
        supplier_id (Optional[int]): Foreign key to supplier
        supplier (Optional[Supplier]): Related supplier
        number (Optional[str]): Invoice number
        date (date): Invoice date
        total_sum (Optional[Decimal]): Total sum
        items (List[InvoiceItem]): List of invoice items
    """
    __tablename__ = "invoices"
    
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_sum: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier", back_populates="invoices")
    items: Mapped[List["InvoiceItem"]] = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    
    @validates('number')
    def validate_number(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate invoice number."""
        if value:
            value = value.strip()
            if not value:
                raise ValueError("Invoice number cannot be empty string")
            return value
        return None
    
    @validates('date')
    def validate_date(self, key: str, value: date) -> date:
        """Validate invoice date."""
        if not value:
            raise ValueError("Invoice date is required")
        if isinstance(value, datetime):
            return value.date()
        return value
    
    @validates('total_sum')
    def validate_total_sum(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate total sum."""
        if value is not None and value < 0:
            raise ValueError("Total sum cannot be negative")
        return value
    
    def __str__(self) -> str:
        """Return string representation of the invoice."""
        return f"Накладная №{self.number or 'б/н'} от {self.date}"
