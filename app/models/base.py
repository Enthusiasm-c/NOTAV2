"""
Базовый класс моделей + алиас первичного ключа
----------------------------------------------
Теперь alias создаёт **новый** Column для каждой модели ─
никаких «дубликатов id» больше не будет.
"""

from __future__ import annotations

from typing import Annotated, TypeAlias

from sqlalchemy import Integer, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# единый naming-convention (Alembic diff-ы)
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ── 💡 TypeAlias, а НЕ готовый Column! ─────────────────────────────────────────
IntPK: TypeAlias = Annotated[
    int,
    mapped_column(Integer, primary_key=True, autoincrement=True),
]
