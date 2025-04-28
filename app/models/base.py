"""
Базовый класс моделей + полезные алиасы
---------------------------------------
* Единая metadata с naming-convention
* Готовый `int_pk` для простого авто-PK
"""

from __future__ import annotations

from typing import Annotated

from sqlalchemy import Integer, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ――― naming-convention для корректных Alembic-diffʼов ―――――――――――――――――
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ――― Алиасы, чтобы не повторять одно и то же в моделях ――――――――――――――――
int_pk: Annotated[Mapped[int], mapped_column(Integer, primary_key=True, autoincrement=True)] = mapped_column(  # type: ignore[assignment]
    Integer, primary_key=True, autoincrement=True
)
