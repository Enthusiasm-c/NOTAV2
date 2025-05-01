"""
Supplier model for Nota V2.

This module defines the Supplier model which represents suppliers in the database.
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
import re

from sqlalchemy import Integer, String, ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import IntPK

if TYPE_CHECKING:
    from .invoice import Invoice

class Supplier(IntPK):
    """
    Supplier model representing suppliers in the database.
    
    Attributes:
        id (int): Primary key
        name (str): Supplier name
        inn (str): Tax identification number
        kpp (str): Tax registration reason code
        address (Optional[str]): Legal address
        phone (Optional[str]): Contact phone number
        email (Optional[str]): Contact email
        comment (Optional[str]): Additional notes
        invoices (List[Invoice]): List of related invoices
    """
    __tablename__ = "suppliers"
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    inn: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    kpp: Mapped[str] = mapped_column(String(9), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="supplier")
    
    @validates('name')
    def validate_name(self, key: str, value: str) -> str:
        """Validate supplier name."""
        if not value or not value.strip():
            raise ValueError("Supplier name cannot be empty")
        return value.strip()
    
    @validates('inn')
    def validate_inn(self, key: str, value: str) -> str:
        """Validate INN (tax identification number)."""
        if not value or not value.strip():
            raise ValueError("INN cannot be empty")
        value = value.strip()
        if not re.match(r'^\d{10}|\d{12}$', value):
            raise ValueError("INN must be 10 or 12 digits")
        return value
    
    @validates('kpp')
    def validate_kpp(self, key: str, value: str) -> str:
        """Validate KPP (tax registration reason code)."""
        if not value or not value.strip():
            raise ValueError("KPP cannot be empty")
        value = value.strip()
        if not re.match(r'^\d{9}$', value):
            raise ValueError("KPP must be 9 digits")
        return value
    
    @validates('phone')
    def validate_phone(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate phone number."""
        if value:
            value = value.strip()
            if not re.match(r'^\+?[\d\s\-\(\)]+$', value):
                raise ValueError("Invalid phone number format")
            return value
        return None
    
    @validates('email')
    def validate_email(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate email address."""
        if value:
            value = value.strip()
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                raise ValueError("Invalid email format")
            return value
        return None
    
    def __str__(self) -> str:
        """Return string representation of the supplier."""
        return f"{self.name} (ИНН: {self.inn})"
