"""
Alembic environment for Nota V2
───────────────────────────────
* Добавляет корень проекта (/opt/notav2) в sys.path
* Импортирует ВСЕ модели, чтобы autogenerate видел таблицы
"""

from __future__ import annotations

import asyncio
import logging.config
import sys
from pathlib import Path
from typing import AsyncGenerator

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── PYTHONPATH ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # /opt/notav2
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# теперь можно импортировать настройки и модели
from app.config import settings  # noqa: E402
import app.models  # noqa: F401,E402  ← ВАЖНО: импортирует всё

# ── Alembic config ──────────────────────────────────────────────────────
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

# Optional: включите логирование Alembic
logging.config.fileConfig(config.config_file_name)

target_metadata = app.models.Base.metadata  # noqa: E402


# ── Runners ─────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """CLI-режим – генерируем SQL без подключения к БД."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Основной режим – подключения к БД и выполнение миграций."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),  # type: ignore[arg-type]
        prefix="sqlalchemy.",
        future=True,
        pool_pre_ping=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
        )

        async with context.begin_transaction():
            await connection.run_sync(context.run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
