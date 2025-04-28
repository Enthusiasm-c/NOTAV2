# scripts/load_seed_data.py
"""
Bulk-загрузка справочников (suppliers / products / lookups) из CSV.
------------------------------------------------------------------

Примеры:
    python -m scripts.load_seed_data suppliers data/base_suppliers.csv
    python -m scripts.load_seed_data products  data/base_products.csv
    python -m scripts.load_seed_data lookups   data/product_name_lookup.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Any, Iterable

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, engine
from app.models import Product, Supplier, ProductNameLookup

# --------------------------------------------------------------------------- #
MODELS: dict[str, type[sa.orm.DeclarativeBase]] = {
    "products": Product,
    "suppliers": Supplier,
    "lookups": ProductNameLookup,
}


def _iter_rows(csv_path: Path) -> Iterable[dict[str, Any]]:
    """Чтение CSV-файла в виде dict-строк."""
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # пустые ячейки превращаем в None
            yield {k: (v or None) for k, v in row.items()}


async def _bulk_insert(session: AsyncSession, model: type[sa.orm.DeclarativeBase], rows: list[dict[str, Any]]) -> None:
    """Диалект-зависимая вставка с игнором дубликатов."""
    if not rows:
        return

    dialect_name = str(engine.url).split(":", 1)[0]

    if dialect_name == "postgresql":
        # используем insert … on_conflict_do_nothing()
        from sqlalchemy.dialects.postgresql import insert as pg_insert  # type: ignore
        stmt = pg_insert(model).values(rows).on_conflict_do_nothing()
        await session.execute(stmt)
    else:
        # надёжно, но медленнее: upsert через merge()
        for row in rows:
            session.merge(model(**row))  # type: ignore[arg-type]


async def _load(kind: str, csv_file: Path) -> None:
    model = MODELS[kind]
    rows = list(_iter_rows(csv_file))

    async with SessionLocal() as session:
        await _bulk_insert(session, model, rows)
        await session.commit()

    print(f"✓ imported {len(rows)} rows into {kind}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=MODELS.keys(), help="Что загружаем")
    parser.add_argument("csv_path", type=Path, help="Путь к CSV")
    args = parser.parse_args()

    if not args.csv_path.exists():
        raise SystemExit(f"CSV not found: {args.csv_path}")

    asyncio.run(_load(args.type, args.csv_path))


if __name__ == "__main__":
    main()
