"""
app.models package
──────────────────
Импортирует все модели одним махом:

    from app.models import Product, Supplier, Base, …

Важно: **порядок** имеет значение – зависимые классы идут ниже базовых.
"""

from __future__ import annotations

from app.config import settings  # noqa: F401

from .base import Base           # noqa: F401
from .supplier import Supplier   # noqa: F401
from .product import Product     # noqa: F401
from .product_name_lookup import ProductNameLookup  # noqa: F401
from .invoice import Invoice     # noqa: F401
from .invoice_item import InvoiceItem  # noqa: F401
from .invoice_name_lookup import InvoiceNameLookup  # ← новая модель  # noqa: F401

__all__: list[str] = [
    "settings",
    "Base",
    "Supplier",
    "Product",
    "ProductNameLookup",
    "Invoice",
    "InvoiceItem",
    "InvoiceNameLookup",
]
