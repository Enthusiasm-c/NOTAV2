"""Общий Base + алиасы для колонок-шаблонов."""
from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Единый declarative-base проекта."""


# единый «шорткат» для PK-колонок
IntPK: type[Mapped[int]] = mapped_column(Integer, primary_key=True, autoincrement=True)

__all__ = ["Base", "IntPK"]
