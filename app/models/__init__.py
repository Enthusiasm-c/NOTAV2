"""
app.models package
──────────────────
Собирает вместе все модели и настройки, чтобы их можно было импортировать одной строкой:

    from app.models import Base, Product, Supplier …
"""

from __future__ import annotations

# Настройки берём из корневого app.config
from app.config import settings  # noqa: F401

# Базовый класс и все модели
from .base import Base  # noqa: F401
from .supplier import Supplier  # noqa: F401
from .product import Product  # noqa: F401
from .product_name_lookup import ProductNameLookup  # noqa: F401
from .invoice import Invoice  # noqa: F401
from .invoice_item import InvoiceItem  # noqa: F401

__all__: list[str] = [
    "settings",
    "Base",
    "Supplier",
    "Product",
    "ProductNameLookup",
    "Invoice",
    "InvoiceItem",
]
