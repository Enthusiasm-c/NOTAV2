"""
Модели SQLAlchemy ORM для Nota V2.

Все модели собраны здесь, чтобы один общий импорт:
    from app.models import Supplier, Product  # и т.д.

По-прежнему можно импортировать каждую модель отдельно:
    from app.models.product import Product
"""

from __future__ import annotations

# Базовый класс для всех моделей
from .base import Base                      # noqa: F401

# Первичные таблицы (без внешних ключей)
from .supplier import Supplier              # noqa: F401
from .product import Product                # noqa: F401

# Вторичные (подчиненные) таблицы
from .invoice import Invoice                # noqa: F401
from .invoice_item import InvoiceItem       # noqa: F401
from .product_name_lookup import ProductNameLookup  # noqa: F401
