"""
app.models package
──────────────────
• Сводит воедино все модели и экспортирует их в __all__,  
  чтобы удобнее было писать «короткие» импорты вида  
  `from app.models import Product`.
• Никакой исполняемой логики здесь нет – только импорт.
"""

from __future__ import annotations

# Настройки (могут понадобиться при инициализации других модулей)
from app.config import settings  # noqa: F401  (оставляем для совместимости)

# Базовый класс declarative-моделей
from .base import Base  # noqa: F401

# Сами модели
from .supplier import Supplier  # noqa: F401
from .product import Product  # noqa: F401
from .product_name_lookup import ProductNameLookup  # noqa: F401
from .invoice import Invoice  # noqa: F401
from .invoice_item import InvoiceItem  # noqa: F401

__all__: list[str] = [
    "Base",
    "Supplier",
    "Product",
    "ProductNameLookup",
    "Invoice",
    "InvoiceItem",
]
