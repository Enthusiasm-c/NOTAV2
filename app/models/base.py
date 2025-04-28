# app/models/base.py
"""
Общие вещи для всех ORM-моделей
──────────────────────────────
* Base – декларативный базовый класс
* int_pk / str_pk – готовые тип-алиасы для первичных ключей
"""

from __future__ import annotations

import typing as _t

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ───────────────────── базовый класс ────────────────────────────────


class Base(DeclarativeBase):  # pragma: no cover
    """Базовый класс для declarative-моделей."""
    repr_running = False  # отключаем громоздкий repr у вложенных моделей


# ───────────────────── хэдим функции-алиасы PK ──────────────────────


def _pk_column(sql_type) -> _t.Any:  # noqa: ANN401
    """Единое место, если захотим менять common-опции PK-столбцов."""
    return mapped_column(sql_type, primary_key=True, autoincrement=True)


# целочисленный PK (int → BIGINT / SERIAL зависит от СУБД)
int_pk: _t.Annotated[int, _pk_column(int)]  # type: ignore[var-annotated]

# строковый PK (UUID / CHAR(36) и т. п.)
str_pk: _t.Annotated[str, _pk_column(String(36))]  # type: ignore[var-annotated]
