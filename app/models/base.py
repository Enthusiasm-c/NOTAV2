"""
Base model and mixins for Nota V2.

This module defines the base SQLAlchemy model and common mixins used by other models.
"""

from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

class IntPK(Base):
    """
    Mixin that adds an integer primary key column.
    
    Attributes:
        id (int): Primary key
    """
    __abstract__ = True
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
