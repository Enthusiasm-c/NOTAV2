"""
ProductNameLookup model for Nota V2.

This module defines the ProductNameLookup model which maps alternative product names
to actual products in the database.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, String, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import IntPK

if TYPE_CHECKING:
    from .product import Product

class ProductNameLookup(IntPK):
    """
    ProductNameLookup model for mapping alternative product names.
    
    Attributes:
        id (int): Primary key
        alias (str): Alternative product name
        product_id (int): Foreign key to product
        product (Product): Related product
        comment (Optional[str]): Additional notes about this mapping
    """
    __tablename__ = "product_name_lookup"
    
    alias: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    product: Mapped["Product"] = relationship("Product")
    
    @validates('alias')
    def validate_alias(self, key: str, value: str) -> str:
        """Validate alternative product name."""
        if not value or not value.strip():
            raise ValueError("Alternative product name cannot be empty")
        return value.strip()
    
    def __str__(self) -> str:
        """Return string representation of the lookup entry."""
        return f"{self.alias} -> {self.product.name}"
