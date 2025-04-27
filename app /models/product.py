from sqlalchemy import Column, Integer, String
from app.db import Base

class Product(Base):
    """Product directory"""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    unit = Column(String(32), nullable=True)
