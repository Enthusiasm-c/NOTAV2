# app/utils/xml_generator.py
"""
Формирование XML для Syrve (упрощённый вариант для MVP).
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import date

def build_xml(data: dict) -> str:
    """
    data = {
        "supplier": "ООО Ромашка",
        "buyer": "ООО Ресторан",
        "date": "2025-04-10",
        "positions": [
            {"name":"Товар А","quantity":5,"unit":"кг","price":100.0,"sum":500.0},
            …
        ],
        "total_sum": 900.0
    }
    """
    root = ET.Element("SyrveDocument")

    ET.SubElement(root, "Supplier").text = data["supplier"]
    ET.SubElement(root, "Buyer").text    = data["buyer"]
    ET.SubElement(root, "Date").text     = data.get("date", str(date.today()))

    items = ET.SubElement(root, "Items")
    for p in data["positions"]:
        item = ET.SubElement(items, "Item")
        ET.SubElement(item, "Name").text     = p["name"]
        ET.SubElement(item, "Quantity").text = str(p["quantity"])
        ET.SubElement(item, "Unit").text     = p.get("unit") or ""
        ET.SubElement(item, "Price").text    = f"{p.get('price', 0):.2f}"
        ET.SubElement(item, "Sum").text      = f"{p.get('sum', 0):.2f}"

    ET.SubElement(root, "TotalSum").text = f"{data.get('total_sum', 0):.2f}"

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode()
