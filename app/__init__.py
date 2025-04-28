"""
app
───
Инициализатор пакета.

* Позволяет короткие импорты::

      from app import settings, Product, Supplier, Base

* Экспортирует сессию и движок БД (пригодится в CLI-скриптах).
* Добавляет shim для совместимости: `import app.base` → `app.models.base`.
"""

from __future__ import annotations

# ───────── базовые настройки ─────────
from .config import settings  # noqa: F401  ← .env / DB-URL, и т.п.

# ───────── модели и Base ─────────────
from .models import (  # noqa: F401
    Base,
    Supplier,
    Product,
    Invoice,
    InvoiceItem,
    ProductNameLookup,
)

# ───────── сессия и движок ───────────
from .db import SessionLocal, engine  # noqa: F401

__all__ = [
    # конфиг
    "settings",
    # ORM-база и модели
    "Base",
    "Supplier",
    "Product",
    "Invoice",
    "InvoiceItem",
    "ProductNameLookup",
    # БД
    "SessionLocal",
    "engine",
]

# ───────── shim: app.base → app.models.base ─────────
import sys as _sys

_sys.modules[f"{__name__}.base"] = _sys.modules["app.models.base"]
