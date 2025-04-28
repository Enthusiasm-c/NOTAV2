"""
app package init
────────────────
* Делает «короткие» импорты ― `from app import Product, Base …`
* Ничего лишнего не исполняет (важно для pytest и alembic).
"""

from __future__ import annotations

# ── настройки доступны одной строкой ───────────────────────────────────────────
from .config import settings  # noqa: F401

# ── модели (подтягиваем через app.models, где уже собран Base) ────────────────
from .models import (  # noqa: F401
    Base,
    Supplier,
    Product,
    ProductNameLookup,
    Invoice,
    InvoiceItem,
)

__all__ = [
    "settings",
    # модели
    "Base",
    "Supplier",
    "Product",
    "ProductNameLookup",
    "Invoice",
    "InvoiceItem",
]
