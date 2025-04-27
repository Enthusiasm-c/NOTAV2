# alembic/env.py
"""
Async Alembic environment for Nota V2
──────────────────────────────────────
* SQLAlchemy 2.0 + asyncpg
* target_metadata = Base.metadata
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── добавить корень проекта в PYTHONPATH ───────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /opt/notav2
sys.path.append(str(PROJECT_ROOT))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    async_engine_from_config,
)

from app.models.base import Base  # noqa: E402

target_metadata = Base.metadata
config = context.config


# ────────────────────────── engine factory ─────────────────────────────
def get_async_engine() -> AsyncEngine:
    return async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )


# ────────────────────────── offline mode ───────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ────────────────────────── online mode ────────────────────────────────
def do_run_migrations(connection):  # sync-функция!
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = get_async_engine()
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()


# ────────────────────────── entrypoint ─────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
