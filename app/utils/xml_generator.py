"""
Формирование XML для Syrve.
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, Any, List

def build_xml(data: Dict[str, Any]) -> str:
    """
    Формирует XML-документ для Syrve из данных накладной.
    
    Ожидаемая структура data:
    {
        "supplier": "ООО Ромашка",
        "buyer": "ООО Ресторан",
        "date": "2025-04-10",
        "positions": [
            {"name":"Товар А","quantity":5,"unit":"кг","price":100.0,"sum":500.0},
            ...
        ],
        "total_sum": 900.0
    }
    
    :param data: Словарь с данными накладной
    :return: XML строка с кодировкой UTF-8 и XML-декларацией
    """
    # Создаем корневой элемент
    root = ET.Element("SyrveDocument")
    
    # Добавляем основные данные
    if "supplier" in data:
        ET.SubElement(root, "Supplier").text = str(data["supplier"])
    if "buyer" in data:
        ET.SubElement(root, "Buyer").text = str(data["buyer"])
    
    # Обрабатываем дату (с проверкой формата)
    if "date" in data:
        ET.SubElement(root, "Date").text = str(data["date"])
    else:
        ET.SubElement(root, "Date").text = str(date.today())
    
    # Добавляем позиции
    items = ET.SubElement(root, "Items")
    for p in data.get("positions", []):
        item = ET.SubElement(items, "Item")
        
        if "name" in p:
            ET.SubElement(item, "Name").text = str(p["name"])
        
        if "quantity" in p:
            ET.SubElement(item, "Quantity").text = str(p["quantity"])
        
        if "unit" in p:
            ET.SubElement(item, "Unit").text = str(p.get("unit", ""))
        
        if "price" in p:
            try:
                price = float(p["price"])
                ET.SubElement(item, "Price").text = f"{price:.2f}"
            except (ValueError, TypeError):
                ET.SubElement(item, "Price").text = "0.00"
        
        if "sum" in p:
            try:
                sum_value = float(p["sum"])
                ET.SubElement(item, "Sum").text = f"{sum_value:.2f}"
            except (ValueError, TypeError):
                ET.SubElement(item, "Sum").text = "0.00"
    
    # Добавляем итоговую сумму
    if "total_sum" in data:
        try:
            total = float(data["total_sum"])
            ET.SubElement(root, "TotalSum").text = f"{total:.2f}"
        except (ValueError, TypeError):
            # Рассчитываем из позиций
            total = 0.0
            for p in data.get("positions", []):
                try:
                    total += float(p.get("sum", 0)) if p.get("sum") else 0
                except (ValueError, TypeError):
                    pass
            ET.SubElement(root, "TotalSum").text = f"{total:.2f}"
    
    # Преобразуем в строку с XML-декларацией
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
