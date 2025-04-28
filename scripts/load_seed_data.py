#!/usr/bin/env python
"""
Импорт CSV-файлов в базу (seed-данные).

Использование:
    python -m scripts.load_seed_data suppliers data/base_suppliers.csv
    python -m scripts.load_seed_data products  data/base_products.csv
    python -m scripts.load_seed_data lookups   data/product_name_lookup.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Generator, Type

from sqlalchemy import insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Product, Supplier, ProductNameLookup

MODEL_MAP: dict[str, Type] = {
    "products": Product,
    "suppliers": Supplier,
    "lookups": ProductNameLookup,
}


def _iter_rows(csv_path: Path) -> Generator[dict[str, str], None, None]:
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield {k.strip(): v.strip() for k, v in row.items() if v is not None}


async def _load(kind: str, csv_path: Path) -> None:
    model = MODEL_MAP[kind]
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return

    engine = create_async_engine(settings.database_url, echo=False, future=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    allowed_cols = {c.name for c in model.__table__.columns}

    async with async_session() as session:  # type: Session
        rows = [{k: v for k, v in row.items() if k in allowed_cols} for row in _iter_rows(csv_path)]

        if engine.dialect.name == "sqlite":  # «ON CONFLICT DO NOTHING» по-sqlite
            stmt = sqlite_insert(model).values(rows).prefix_with("OR IGNORE")
            await session.execute(stmt)
        else:  # Postgres / MySQL
            stmt = insert(model).values(rows).on_conflict_do_nothing()
            await session.execute(stmt)

        await session.commit()

        # для контроля — сколько строк в таблице
        total: int = (await session.execute(select(model))).rowcount or 0
        print(f"✓ {kind:<9} imported {len(rows):>5} → total {total}")


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=MODEL_MAP.keys())
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    asyncio.run(_load(args.type, args.csv_path))


if __name__ == "__main__":  # pragma: no cover
    main()
