"""
Supplier model for Nota V2.

This module defines the Supplier model which represents suppliers in the database.
"""

from __future__ import annotations
from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import IntPK

class Supplier(IntPK):
    """
    Supplier model representing suppliers in the database.
    
    Attributes:
        id (int): Primary key
        name (str): Supplier name
        inn (Optional[str]): Tax identification number
        kpp (Optional[str]): Tax registration reason code
        address (Optional[str]): Legal address
        phone (Optional[str]): Contact phone number
        email (Optional[str]): Contact email
        comment (Optional[str]): Additional notes
    """
    __tablename__ = "suppliers"
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    kpp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    def __str__(self) -> str:
        """Return string representation of the supplier."""
        return f"{self.name} (ИНН: {self.inn or 'не указан'})"
