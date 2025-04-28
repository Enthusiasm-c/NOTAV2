# app/models/base.py
"""
Общий «скелет» для всех ORM-моделей Nota V2.

* Base — корневой класс declarative-моделей.
* int_pk() — небольшая утилита, дающая стандартное
  авто-инкрементное `INTEGER PRIMARY KEY`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Integer
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)


class _Base(DeclarativeBase):
    """Базовый declarative-класс без __tablename__."""

    pass


class Base(_Base):
    """
    Общий предок **всех** таблиц.

    Автоматически формирует `__tablename__` по имени
    класса в snake_case (ProductCategory → product_category).
    """

    __abstract__ = True  # не создавать собственную таблицу

    @declared_attr.directive
    def __tablename__(cls) -> str:  # type: ignore[override]
        name = cls.__name__
        snake = "".join(
            f"_{c.lower()}" if c.isupper() else c for c in name
        ).lstrip("_")
        return snake


def int_pk() -> Mapped[int]:
    """
    Быстрый способ объявить «простой» PK:

    ```python
    id: Mapped[int] = int_pk()
    ```
    """
    return mapped_column(Integer, primary_key=True, autoincrement=True)  # type: ignore[return-value]


__all__: list[str] = ["Base", "int_pk"]
