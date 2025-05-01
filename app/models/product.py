"""
Product model for Nota V2.

This module defines the Product model which represents products in the database.
"""

from __future__ import annotations
from typing import Optional
from decimal import Decimal

from sqlalchemy import Integer, String, Float, event
from sqlalchemy.orm import Mapped, mapped_column, validates

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
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    @validates('name')
    def validate_name(self, key: str, value: str) -> str:
        """Validate product name."""
        if not value or not value.strip():
            raise ValueError("Product name cannot be empty")
        return value.strip()
    
    @validates('code')
    def validate_code(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate product code."""
        if value is not None:
            if not value.strip():
                raise ValueError("Product code cannot be empty")
            return value.strip()
        return None
    
    @validates('unit')
    def validate_unit(self, key: str, value: str) -> str:
        """Validate unit of measurement."""
        if not value or not value.strip():
            raise ValueError("Unit cannot be empty")
        return value.strip()
    
    @validates('price')
    def validate_price(self, key: str, value: Optional[float]) -> Optional[float]:
        """Validate price."""
        if value is not None and value < 0:
            raise ValueError("Price cannot be negative")
        return value
    
    def __str__(self) -> str:
        """Return string representation of the product."""
        return f"{self.name} ({self.unit})"
