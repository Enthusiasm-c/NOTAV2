"""
app package init
────────────────
* Делает «короткие» импорты:   `from app import Product`
* Экспортирует Base и все основные модели.
* Не выполняет лишнего кода при импорте (важно для тестов/Alembic).
"""

from __future__ import annotations

# ── настройки приложения ──────────────────────────────────────────────────────
from .config import settings  # noqa: F401

# ── модели и базовый класс ────────────────────────────────────────────────────
from .models.base import Base  # noqa: F401
from .models.supplier import Supplier  # noqa: F401
from .models.product import Product  # noqa: F401
from .models.product_name_lookup import ProductNameLookup  # noqa: F401
from .models.invoice import Invoice  # noqa: F401
from .models.invoice_item import InvoiceItem  # noqa: F401

__all__: list[str] = [
    "settings",
    "Base",
    "Supplier",
    "Product",
    "ProductNameLookup",
    "Invoice",
    "InvoiceItem",
]
