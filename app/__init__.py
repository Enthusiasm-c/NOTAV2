"""
app.models package init
───────────────────────
* Соединяет все модели в единое пространство имён,
  чтобы можно было писать `from app.models import Product, Base …`.
* В __all__ обязательно включаем Base и каждую модель.
"""

from __future__ import annotations

# порядок важен: Base первым, остальные следом
from .base import Base                     # noqa: F401
from .supplier import Supplier             # noqa: F401
from .product import Product               # noqa: F401
from .product_name_lookup import ProductNameLookup  # noqa: F401
from .invoice import Invoice               # noqa: F401
from .invoice_item import InvoiceItem      # noqa: F401

__all__ = [
    "Base",
    "Supplier",
    "Product",
    "ProductNameLookup",
    "Invoice",
    "InvoiceItem",
]
