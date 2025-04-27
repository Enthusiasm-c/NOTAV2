def make_invoice_markdown(draft: dict) -> str:
    """Формирует Markdown-таблицу накладной (№, Наименование, Кол-во × Цена, Сумма)"""
    header = "| № | Наименование | Кол-во | Ед. | Цена | Сумма |\n|---|--------------|--------|-----|------|-------|"
    rows = []
    positions = draft.get("positions", [])
    for i, pos in enumerate(positions, 1):
        rows.append(
            f'| {i} | {pos.get("name", "")} | {pos.get("quantity", "")} | {pos.get("unit", "")} | '
            f'{pos.get("price", "")} | {pos.get("sum", "")} |'
        )
    total = sum(float(pos.get("sum", 0) or 0) for pos in positions)
    footer = f"\n\n**Итого:** `{total:.2f}`"
    return "\n".join([header] + rows) + footer
