# alembic/env.py
"""
Async Alembic environment for Nota V2
─────────────────────────────────────
* Работает с SQLAlchemy 2.0 (async engine).
* target_metadata = Base.metadata (из app.models.base).
* Добавляем корень проекта в PYTHONPATH, чтобы импортировать пакет `app`
  даже если Alembic запущен из-под cron/CI.

Команды:
    alembic revision --autogenerate -m "comment"
    alembic upgrade head
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import AsyncGenerator

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, async_engine_from_config

# ────────────────────────── PYTHONPATH ────────────────────────────────
# /opt/notav2/alembic/env.py  →  parents[1] == /opt/notav2
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# ────────────────────────── App metadata ──────────────────────────────
from app.models.base import Base  # noqa: E402

target_metadata = Base.metadata

# ────────────────────────── Logging setup ─────────────────────────────
config = context.config
logging.basicConfig()
logger = logging.getLogger("alembic.env")

# ────────────────────────── Async engine factory ──────────────────────
def get_async_engine() -> AsyncEngine:
    """Create AsyncEngine using config in alembic.ini."""
    return async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )


# ────────────────────────── Offline mode ──────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in --sql mode."""
    url: str = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ────────────────────────── Online mode ───────────────────────────────
async def run_async_migrations(connection: AsyncConnection) -> None:
    """Actual migration logic executed inside an async connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    async with context.begin_transaction():
        await connection.run_sync(context.run_migrations)


async def run_migrations_online() -> None:
    """Create engine → async connection → run migrations."""
    connectable = get_async_engine()
    async with connectable.connect() as connection:
        await run_async_migrations(connection)

    await connectable.dispose()


# ────────────────────────── Entrypoint ────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
