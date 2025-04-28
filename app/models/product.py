from __future__ import annotations

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class Product(Base):
    """Номенклатура клиента Syrve (или локальная)."""

    __tablename__ = "products"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String, unique=True, index=True, nullable=False)
    unit: str | None = Column(String, nullable=True)  # базовая единица

    # ――― reverse link ―――
    items = relationship(
        "InvoiceItem",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
