#!/usr/bin/env python
"""
scripts/load_seed_data.py
─────────────────────────
Импорт начальных CSV-данных в БД Nota V2.

▪️ Поддерживает 3 «типа» CSV:
   • products      → app.models.product.Product
   • suppliers     → app.models.supplier.Supplier
   • lookups       → app.models.product_name_lookup.InvoiceNameLookup

▪️ Формат командной строки
   poetry run python scripts/load_seed_data.py <type> <csv_path>

▪️ Примеры
   poetry run python scripts/load_seed_data.py products  data/base_products.csv
   poetry run python scripts/load_seed_data.py suppliers data/base_suppliers.csv
   poetry run python scripts/load_seed_data.py lookups   data/product_name_lookup.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Iterable

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.product_name_lookup import InvoiceNameLookup
from app.models.base import Base  # ← metadata для create_all()


TABLES = {
    "products": Product,
    "suppliers": Supplier,
    "lookups": InvoiceNameLookup,
}


def _parse_csv(csv_path: Path) -> Iterable[dict]:
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Убираем пустые колонки / пробелы
            yield {k.strip(): v.strip() for k, v in row.items() if v.strip()}


async def _load(table_key: str, csv_path: Path) -> None:
    model = TABLES[table_key]

    # one engine per script – ок
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # Если база чистая – создаём таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        items = list(_parse_csv(csv_path))
        if not items:
            print("⚠️  CSV пустой – нет чего импортировать")
            return

        stmt = insert(model).values(items).on_conflict_do_nothing()
        await session.execute(stmt)
        await session.commit()

    print(f"✓  {len(items)} строк из «{csv_path}» → таблица {model.__tablename__}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Load seed data CSV → DB")
    ap.add_argument("type", choices=TABLES.keys(), help="Тип данных")
    ap.add_argument("csv_path", type=Path, help="Путь к CSV-файлу")
    args = ap.parse_args()

    asyncio.run(_load(args.type, args.csv_path))


if __name__ == "__main__":
    main()
