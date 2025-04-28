"""
app package init
────────────────
* Декларативно «выставляет наружу» то, чем пользуются остальные части проекта.
* Ничего лишнего не исполняет при импорте (важно для pytest и Alembic).
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# Базовые настройки доступны одной строкой
from .config import settings  # noqa: F401

# ──────────────────────────────────────────────────────────────────────────────
# Модели, которые часто нужны за пределами `app.models`
from .models.product import Product                # noqa: F401
from .models.supplier import Supplier              # noqa: F401
from .models.product_name_lookup import ProductNameLookup  # noqa: F401
from .models.invoice import Invoice                # noqa: F401
from .models.invoice_item import InvoiceItem       # noqa: F401

# Base нужна Alembic-у и тестам, чтобы быстро получать metadata
from .models.base import Base                      # noqa: F401

__all__ = [
    # настройки
    "settings",
    # модели
    "Product",
    "Supplier",
    "ProductNameLookup",
    "Invoice",
    "InvoiceItem",
    # metadata
    "Base",
]
