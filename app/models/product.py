from __future__ import annotations

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPK


class Product(Base):
    """
    Номенклатура товаров (master-data из POS/ERP).

    * `id` (PK) хранится как строка — совпадает с UUID из исходной системы  
    * `measure_name` – «кг», «л», «шт» и т.п.  
    * `is_ingredient` – признак «сырья» для кухни (опционально)
    """

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    measure_name: Mapped[str | None] = mapped_column(String(64))
    is_ingredient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ───── связи ────────────────────────────────────────────────────────────
    name_lookups: Mapped[list["ProductNameLookup"]] = relationship(
        "ProductNameLookup",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # ───── вспомогательные методы ──────────────────────────────────────────
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.id}: {self.name!r}>"
