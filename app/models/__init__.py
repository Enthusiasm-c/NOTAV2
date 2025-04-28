# app/models/__init__.py
"""
Собираем все SQLAlchemy-модели в одном месте
────────────────────────────────────────────
Импортируя `app.models`, вы получаете доступ ко всем моделям
и гарантируете их регистрацию в MetaData (важно для Alembic).
"""

from __future__ import annotations

# порядок важен для ForeignKey / relationship
from .supplier import Supplier          # noqa: F401
from .product import Product            # noqa: F401
from .invoice import Invoice            # noqa: F401
from .invoice_item import InvoiceItem   # noqa: F401
from .product_name_lookup import ProductNameLookup  # noqa: F401

__all__ = [
    "Supplier",
    "Product",
    "Invoice",
    "InvoiceItem",
    "ProductNameLookup",
]
