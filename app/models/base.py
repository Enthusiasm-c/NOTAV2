# app/models/base.py
"""
Общий базовый модуль для всех ORM-моделей
─────────────────────────────────────────
* Base    — декларативный базовый класс
* int_pk / str_pk — готовые тип-алиасы для PK-столбцов
"""

from __future__ import annotations

from typing import Annotated

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, mapped_column


# ────────────────────────── базовый класс ──────────────────────────


class Base(DeclarativeBase):  # pragma: no cover
    """Единая точка входа для всех ORM-моделей (metadata живёт здесь)."""
    pass


# ─────────────────────── тип-алиасы первичного ключа ───────────────

# Используем «ленивую» декларацию через typing.Annotated:
#   id: Mapped[int_pk]          ← в модели
# Это читабельно и не дублирует mapped_column(...) каждый раз.

int_pk = Annotated[int, mapped_column(primary_key=True, autoincrement=True)]

str_pk = Annotated[
    str,
    mapped_column(String(64), primary_key=True, autoincrement=False),
]
