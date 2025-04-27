# app/models/invoice_name_lookup.py
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.product import Product


class InvoiceNameLookup(Base):
    """
    Справочник «распознанное название → product_id», чтобы бот
    мгновенно находил ранее подтверждённые позиции.
    """
    __tablename__ = "invoice_name_lookup"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parsed_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # удобная навигация ORM → InvoiceNameLookup.product
    product: Mapped["Product"] = relationship(back_populates="name_lookups")
