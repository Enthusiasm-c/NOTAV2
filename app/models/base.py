"""Общий declarative-foundation (SQLAlchemy 2.0)."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, registry, Mapped
from sqlalchemy import MetaData

# единая naming-convention — Alembic любит
_naming = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    }
)

mapper_registry = registry(metadata=_naming)


class Base(DeclarativeBase):
    registry = mapper_registry

    # удобный to-dict для дебага
    def as_dict(self) -> dict[str, str]:
        return {
            k: getattr(self, k)
            for k in self.__mapper__.columns.keys()  # noqa: SLF001
        }
