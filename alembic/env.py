# alembic/env.py
"""
Async-friendly Alembic environment for Nota V2
─────────────────────────────────────────────
* Работает и в offline-, и в online-режимах.
* В online-режиме использует create_async_engine,
  а миграции запускает через conn.run_sync(do_run_migrations).
"""

from __future__ import annotations

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent   # → /opt/notav2
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# --- Nota V2 imports ---------------------------------------------------------
from app.config import settings                           # ← гарантирует PYTHONPATH
import app.models.base                                    # noqa: F401  (метаданные)
# --------------------------------------------------------------------------- #

# Загружаем конфиг-файл alembic.ini (чтобы работали section [loggers] и т.п.)
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# Метаданные всех моделей (Base.metadata уже импортирован строкой выше)
target_metadata = app.models.base.Base.metadata  # type: ignore[attr-defined]

# --------------------------------------------------------------------------- #
#  OFFLINE: вывод SQL в stdout / файл
# --------------------------------------------------------------------------- #
def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# --------------------------------------------------------------------------- #
#  ONLINE: выполняем миграции по живому соединению
# --------------------------------------------------------------------------- #
def do_run_migrations(connection):
    """Синхронная часть: configure + context.run_migrations()."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(
        settings.database_url, pool_pre_ping=True, future=True
    )

    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)

    await connectable.dispose()


# --------------------------------------------------------------------------- #
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
