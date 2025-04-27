# alembic/env.py
"""
Async Alembic environment for Nota V2
─────────────────────────────────────
* SQLAlchemy 2.0 (async engine, asyncpg)
* target_metadata = Base.metadata  ─ для autogenerate
* Добавляем корень проекта в PYTHONPATH до любых импортов `app`,
  чтобы команды Alembic работали из-под CI / cron / systemd.

Команды:
    alembic revision --autogenerate -m "comment"
    alembic upgrade head
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator

# ────────────────────────── PYTHONPATH  ────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /opt/notav2
sys.path.append(str(PROJECT_ROOT))                  # ← ДО импортов app

# ────────────────────────── Alembic / SA  ─────────────────────────────
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    async_engine_from_config,
)

# ────────────────────────── App metadata  ─────────────────────────────
from app.models.base import Base  # noqa: E402

target_metadata = Base.metadata
config = context.config

# ────────────────────────── Logging (по желанию) ──────────────────────
# import logging
# logging.basicConfig(level=logging.INFO)

# ────────────────────────── Engine factory  ───────────────────────────
def get_async_engine() -> AsyncEngine:
    """Создаём AsyncEngine из настроек alembic.ini."""
    return async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )


# ────────────────────────── OFFLINE mode  ─────────────────────────────
def run_migrations_offline() -> None:
    url: str = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ────────────────────────── ONLINE mode  ──────────────────────────────
async def run_async_migrations(connection: AsyncConnection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    async with context.begin_transaction():
        await connection.run_sync(context.run_migrations)


async def run_migrations_online() -> None:
    connectable = get_async_engine()
    async with connectable.connect() as conn:
        await run_async_migrations(conn)
    await connectable.dispose()


# ────────────────────────── Entrypoint  ───────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
