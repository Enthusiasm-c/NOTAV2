"""
ProductNameLookup model for Nota V2.

This module defines the ProductNameLookup model which maps alternative product names
to actual products in the database.
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import IntPK
from .product import Product

class ProductNameLookup(IntPK):
    """
    ProductNameLookup model for mapping alternative product names.
    
    Attributes:
        id (int): Primary key
        alias (str): Alternative product name
        product_id (int): Foreign key to product
        product (Product): Related product
        comment (Optional[str]): Additional notes
    """
    __tablename__ = "product_name_lookup"
    
    alias: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product: Mapped[Product] = relationship(Product)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    def __str__(self) -> str:
        """Return string representation of the lookup entry."""
        return f"{self.alias} -> {self.product.name}"
