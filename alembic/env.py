#!/usr/bin/env python
"""
Alembic environment — используется при создании / выполнении миграций.

* SQLAlchemy 2.0 style
* Асинхронный движок (asyncpg, aiosqlite и т. д.)
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from pathlib import Path
from types import ModuleType
from typing import Sequence

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config

# ─────────────────────────── Приложение ──────────────────────────────
# База и настройки подтягиваются **до** конфигурации Alembic
import app.models  # noqa: F401  ← гарантирует импорт всех моделей
from app.config import settings
from app.models.base import Base  # Base.metadata → target_metadata

# ─────────────────────────── Логи / env vars ─────────────────────────
config = context.config
if config.config_file_name is not None:  # alembic.ini
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Устанавливаем URL БД динамически, чтобы одинаково работал dev / CI / prod
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

# ─────────────────────────── OFFLINE MODE ────────────────────────────
def run_migrations_offline() -> None:
    """Генерация SQL без подключения к БД (alembic upgrade --sql)."""
    url: str = config.get_main_option("sqlalchemy.url")  # уже патчнули выше
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,          # фиксируем изменения типов
    )

    with context.begin_transaction():
        context.run_migrations()


# ─────────────────────────── ONLINE MODE ─────────────────────────────
def _include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """
    Доп. фильтр, если нужно исключить таблицы; сейчас пропускаем всё.
    """
    return True


async def run_migrations_online() -> None:
    """Настраивает AsyncEngine и запускает миграции."""
    connectable: AsyncEngine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:  # type: Connection
        await connection.run_sync(
            lambda sync_conn: context.configure(  # noqa: E731
                connection=sync_conn,
                target_metadata=target_metadata,
                compare_type=True,
                include_object=_include_object,
            )
        )

        async with connection.begin():
            await connection.run_sync(context.run_migrations)

    await connectable.dispose()


# ─────────────────────────── entry-point ─────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
