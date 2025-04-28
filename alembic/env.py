#!/usr/bin/env python
"""
Alembic env (sync; auto-fix async URL)
──────────────────────────────────────
* добавляет BASE_DIR в PYTHONPATH
* если settings.database_url содержит «+asyncpg» — меняем на «+psycopg2»
* offline / online (sync-engine)
"""

from __future__ import annotations
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

# ── PYTHONPATH ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings          # noqa: E402
import app.models                        # noqa: F401, E402
from app.models.base import Base         # noqa: E402

# ── URL: async → sync ───────────────────────────────────────────────────────
sync_url = make_url(settings.database_url)
if sync_url.drivername.endswith("+asyncpg"):
    sync_url = sync_url.set(drivername="postgresql+psycopg2")

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(sync_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        sync_url,
        poolclass=pool.NullPool,
        future=True,
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
