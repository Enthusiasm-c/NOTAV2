"""
app package init
────────────────
* Делает «короткие» импорты вида `from app import Product`
* Ничего лишнего не исполняет при импорте (важно для pytest)
"""

from __future__ import annotations

# Базовые настройки доступны одной строкой
from .config import settings  # noqa: F401

# Модели, которые часто нужны вне `app.models`
from .models.product import Product  # noqa: F401
from .models.invoice import Invoice  # noqa: F401
from .models.invoice_item import InvoiceItem  # noqa: F401

__all__ = [
    "settings",
    "Product",
    "Invoice",
    "InvoiceItem",
]
