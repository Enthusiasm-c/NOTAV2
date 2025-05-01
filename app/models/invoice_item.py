"""
InvoiceItem model for Nota V2.

This module defines the InvoiceItem model which represents items in invoices.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from decimal import Decimal

from sqlalchemy import Integer, String, ForeignKey, Numeric, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import IntPK

if TYPE_CHECKING:
    from .product import Product
    from .invoice import Invoice

class InvoiceItem(IntPK):
    """
    InvoiceItem model representing items in invoices.
    
    Attributes:
        id (int): Primary key
        invoice_id (int): Foreign key to invoice
        invoice (Invoice): Related invoice
        product_id (Optional[int]): Foreign key to product
        product (Optional[Product]): Related product
        name (str): Item name
        quantity (Decimal): Quantity
        unit (str): Unit of measurement
        price (Decimal): Price per unit
        sum (Decimal): Total sum
        comment (Optional[str]): Additional notes
    """
    __tablename__ = "invoice_items"
    
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sum: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
    product: Mapped[Optional["Product"]] = relationship("Product")
    
    @validates('name')
    def validate_name(self, key: str, value: str) -> str:
        """Validate item name."""
        if not value or not value.strip():
            raise ValueError("Item name cannot be empty")
        return value.strip()
    
    @validates('quantity')
    def validate_quantity(self, key: str, value: Decimal) -> Decimal:
        """Validate quantity."""
        if value <= 0:
            raise ValueError("Quantity must be positive")
        return value
    
    @validates('unit')
    def validate_unit(self, key: str, value: str) -> str:
        """Validate unit of measurement."""
        if not value or not value.strip():
            raise ValueError("Unit cannot be empty")
        return value.strip()
    
    @validates('price')
    def validate_price(self, key: str, value: Decimal) -> Decimal:
        """Validate price."""
        if value < 0:
            raise ValueError("Price cannot be negative")
        return value
    
    @validates('sum')
    def validate_sum(self, key: str, value: Decimal) -> Decimal:
        """Validate sum."""
        if value < 0:
            raise ValueError("Sum cannot be negative")
        return value
    
    def __str__(self) -> str:
        """Return string representation of the invoice item."""
        return f"{self.name} ({self.quantity} {self.unit})"
