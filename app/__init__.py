"""
app.models
──────────
Единая точка импорта для всех ORM-моделей и объекта settings.

Пример::
    from app.models import Product, Supplier, settings
"""

from __future__ import annotations

# Конфигурация проекта (DB-URL и т.п.)
from app.config import settings               # noqa: F401  → экспортируем наружу

# Базовый класс и все модели
from .base import Base                        # noqa: F401
from .supplier import Supplier                # noqa: F401
from .product import Product                  # noqa: F401
from .invoice import Invoice                  # noqa: F401
from .invoice_item import InvoiceItem         # noqa: F401
from .product_name_lookup import ProductNameLookup  # noqa: F401

__all__ = [
    "settings",
    "Base",
    "Supplier",
    "Product",
    "Invoice",
    "InvoiceItem",
    "ProductNameLookup",
]
