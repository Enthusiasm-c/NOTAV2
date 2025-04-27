__all__ = ["Product"]

from sqlalchemy import Column, Integer, String
from .base import Base

class Product(Base):
    """Product (справочник товаров)

    Variables:
        id: int
        name: str
        unit: str
    """
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    unit = Column(String(32), nullable=True)
