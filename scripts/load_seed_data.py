# scripts/load_seed_data.py
"""
Bulk-loader for seed CSV data
────────────────────────────
Usage:
    python -m scripts.load_seed_data suppliers <csv>
    python -m scripts.load_seed_data products  <csv>
    python -m scripts.load_seed_data lookups   <csv>

* Работает одинаково с Postgres, SQLite и др.
* session.merge() --> «вставить или обновить», поэтому повторный запуск
  безопасен.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.product_name_lookup import ProductNameLookup


MODELS = {
    "suppliers": Supplier,
    "products": Product,
    "lookups": ProductNameLookup,
}


def _iter_rows(csv_path: Path) -> AsyncIterator[dict]:
    """Sync-generator → async-wrapper (для универсальности)."""
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # нормализуем ключи → lower(), trim()
            yield {k.strip().lower(): v.strip() for k, v in row.items()}


async def _load(kind: str, csv_path: Path) -> None:
    if kind not in MODELS:
        raise SystemExit(f"unknown kind: {kind!r} (choose from {', '.join(MODELS)})")
    model = MODELS[kind]

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    engine = create_async_engine(settings.database_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    total = 0
    async with Session() as session:
        async with session.begin():  # единая транзакция
            async for row in _iter_rows(csv_path):
                obj = model(**row)          # type: ignore[arg-type]
                session.merge(obj)          # «insert or update»
                total += 1

    print(f"✓ loaded {total} rows into {kind} from {csv_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("type", choices=MODELS, help="suppliers / products / lookups")
    ap.add_argument("csv_path", type=Path, help="path to CSV file")
    args = ap.parse_args()

    asyncio.run(_load(args.type, args.csv_path))


if __name__ == "__main__":
    main()
