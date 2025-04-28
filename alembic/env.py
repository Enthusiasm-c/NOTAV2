#!/usr/bin/env python
"""
Alembic – env.py
────────────────
Запускается при autogenerate и upgrade/downgrade.

▪ Добавляем BASE_DIR в PYTHONPATH, чтобы «import app …» всегда находился.  
▪ Импортируем все модели → Alembic видит полную metadata.  
▪ Для миграций используем обычный sync-engine — это безопасно и избавляет
  от ошибок вроде “'_ProxyTransaction' object does not support …”.
"""

from __future__ import annotations

import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine

# ───────────────────────────────────────────────────────────────────────────────
#  PYTHONPATH / BASE_DIR
# ───────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # → /opt/notav2
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# теперь можно безопасно импортировать проект
from app.config import settings              # noqa: E402
import app.models                            # noqa: F401, E402 — регистрирует всё
from app.models.base import Base             # noqa: E402

# ───────────────────────────────────────────────────────────────────────────────
#  Alembic config & metadata
# ───────────────────────────────────────────────────────────────────────────────
config = context.config
fileConfig(config.config_file_name)          # берёт loggers из alembic.ini

target_metadata = Base.metadata


# ───────────────────────────────────────────────────────────────────────────────
#  OFF-line mode (генерирует чистый SQL)
# ───────────────────────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,       # следить за изменением типов колонок
    )

    with context.begin_transaction():
        context.run_migrations()


# ───────────────────────────────────────────────────────────────────────────────
#  ON-line mode (подключаемся к БД и выполняем)
# ───────────────────────────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    connectable = create_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ───────────────────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
