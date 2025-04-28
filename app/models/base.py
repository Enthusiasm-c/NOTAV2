"""
Базовый declarative-класс + тип-шорткаты.
"""

from __future__ import annotations

from typing import Annotated

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, mapped_column


# ──────────────────────────────────────────────────────────────────────────────
# «Коробочный» Base
# ------------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Единый Base для всех моделей."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Шорт-каты для колонок
# ------------------------------------------------------------------------------
# Поле «INTEGER PRIMARY KEY AUTOINCREMENT»
IntPK = Annotated[int, mapped_column(Integer, primary_key=True, autoincrement=True)]
