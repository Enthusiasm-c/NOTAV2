"""
InvoiceItem model for Nota V2.

This module defines the InvoiceItem model which represents items in invoices.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import IntPK
from .product import Product

if TYPE_CHECKING:
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
        quantity (float): Quantity
        unit (str): Unit of measurement
        price (Optional[float]): Price per unit
        comment (Optional[str]): Additional notes
    """
    __tablename__ = "invoice_items"
    
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
    
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    product: Mapped[Optional[Product]] = relationship(Product)
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    def __str__(self) -> str:
        """Return string representation of the invoice item."""
        return f"{self.name} - {self.quantity} {self.unit}"
