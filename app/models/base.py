from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

# --------------------------------------------------------------------------- #
#  Миксин для surrogate-PK: id INTEGER PRIMARY KEY AUTOINCREMENT
# --------------------------------------------------------------------------- #
class IntPK:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

# Базовый declarative-класс для всех ORM-моделей
Base = declarative_base()
