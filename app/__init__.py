# app/__init__.py
"""
Инициализация пакета **app**
────────────────────────────
* Даёт «короткие» импорты:  `from app import Product`
* Настраивает SQLAlchemy-модели, чтобы Base.metadata уже знал обо всех таблицах.
"""

from __future__ import annotations

# --- Конфиг (settings) -------------------------------------------------------
from .config import settings                       # noqa: F401

# --- Модели / SQLAlchemy -----------------------------------------------------
# Важно: сперва Base (там MetaData), потом модели, чтобы мапперы успели настроиться
from .models.base import Base                      # noqa: F401
from .models.product import Product                # noqa: F401
from .models.supplier import Supplier              # noqa: F401
from .models.invoice import Invoice                # noqa: F401
from .models.invoice_item import InvoiceItem       # noqa: F401
from .models.product_name_lookup import (          # noqa: F401
    ProductNameLookup,
)

__all__: list[str] = [
    "settings",
    "Base",
    "Product",
    "Supplier",
    "Invoice",
    "InvoiceItem",
    "ProductNameLookup",
]
