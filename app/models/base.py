"""
Общий базовый класс + миксин с int-PK
"""

from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Общий declarative-base для всех моделей"""
    repr_cols_num = 3  # для __repr__ в MappedAsDataclass (если понадобится)


class IntPK:  # mixin, НЕ наследуемся от Base!
    """Добавляет авто-инкрементный int primary-key"""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
