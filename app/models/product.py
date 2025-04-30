"""
Product model for Nota V2.

This module defines the Product model which represents products in the database.
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy import Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column

from .base import IntPK

class Product(IntPK):
    """
    Product model representing products in the database.
    
    Attributes:
        id (int): Primary key
        name (str): Product name
        code (Optional[str]): Product code
        unit (str): Unit of measurement
        price (Optional[float]): Price per unit
        comment (Optional[str]): Additional notes
    """
    __tablename__ = "products"
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    def __str__(self) -> str:
        """Return string representation of the product."""
        return f"{self.name} ({self.unit})"
