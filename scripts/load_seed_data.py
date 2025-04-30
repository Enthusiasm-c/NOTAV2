#!/usr/bin/env python
"""Заливаем стартовые данные из CSV.

Пример:
    python -m scripts.load_seed_data suppliers data/base_suppliers.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import SessionLocal, engine
from app.models import Supplier, Product, ProductNameLookup, Base  # noqa: F401


def _parse_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


async def _bulk_insert(model, rows: list[dict[str, Any]]) -> None:  # type: ignore[valid-type]
    async with SessionLocal() as session, session.begin():
        stmt = insert(model).values(rows).on_conflict_do_nothing()
        await session.execute(stmt)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=["suppliers", "products", "lookups"])
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    csv_rows = _parse_csv(args.csv_path)

    mapping = {
        "suppliers": (Supplier, {"name": "name", "code": "code"}),
        "products":  (Product, {"name": "name", "unit": "measureName"}),
        "lookups":   (ProductNameLookup, {"alias": "alias", "product_id": "product_id"}),
    }
    model, column_map = mapping[args.type]

    rows = [
        {model_key: row[csv_key] for model_key, csv_key in column_map.items()}
        for row in csv_rows
    ]

    await _bulk_insert(model, rows)
    print(f"✓ inserted {len(rows)} rows into {args.type}")


if __name__ == "__main__":
    asyncio.run(main())
