"""Тестовые данные накладных для проверки форматтера."""

# Накладная без проблем
INVOICE_OK = {
    "supplier": "ООО Продукты",
    "date": "2024-03-15",
    "number": "123-А",
    "positions": [
        {
            "name": "Молоко 3.2%",
            "quantity": 10.0,
            "unit": "л",
            "price": 89.90,
            "sum": 899.00
        },
        {
            "name": "Хлеб белый",
            "quantity": 20.0,
            "unit": "шт",
            "price": 45.50,
            "sum": 910.00
        }
    ]
}

# Накладная с проблемами в количествах
INVOICE_QTY_MISMATCH = {
    "supplier": "ООО Продукты",
    "date": "2024-03-15",
    "number": "124-Б",
    "positions": [
        {
            "name": "Молоко 3.2%",
            "quantity": None,  # Отсутствует количество
            "unit": "л",
            "price": 89.90,
            "sum": 899.00
        },
        {
            "name": "Хлеб белый",
            "quantity": -1.0,  # Отрицательное количество
            "unit": "шт",
            "price": 45.50,
            "sum": 910.00
        }
    ]
}

# Накладная с неизвестными товарами
INVOICE_NOT_FOUND = {
    "supplier": "ООО Продукты",
    "date": "2024-03-15",
    "number": "125-В",
    "positions": [
        {
            "name": "Несуществующий товар",
            "quantity": 1.0,
            "unit": "шт",
            "price": 100.00,
            "sum": 100.00
        },
        {
            "name": "Еще один неизвестный",
            "quantity": 2.0,
            "unit": "кг",
            "price": 200.00,
            "sum": 400.00
        }
    ],
    "parser_comment": "Обнаружены проблемы с распознаванием товаров"
}

# Пустая накладная
INVOICE_EMPTY = {
    "supplier": "ООО Продукты",
    "date": "2024-03-15",
    "number": "126-Г",
    "positions": []
}

# Накладная с проблемами в единицах измерения
INVOICE_UNIT_MISMATCH = {
    "supplier": "ООО Продукты",
    "date": "2024-03-15",
    "number": "127-Д",
    "positions": [
        {
            "name": "Молоко 3.2%",
            "quantity": 10.0,
            "unit": "кг",  # Неверная единица измерения
            "price": 89.90,
            "sum": 899.00
        },
        {
            "name": "Хлеб белый",
            "quantity": 20.0,
            "unit": "",  # Отсутствует единица измерения
            "price": 45.50,
            "sum": 910.00
        }
    ]
}

# Накладная с проблемами в суммах
INVOICE_SUM_MISMATCH = {
    "supplier": "ООО Продукты",
    "date": "2024-03-15",
    "number": "128-Е",
    "positions": [
        {
            "name": "Молоко 3.2%",
            "quantity": 10.0,
            "unit": "л",
            "price": 89.90,
            "sum": 1000.00  # Неверная сумма
        },
        {
            "name": "Хлеб белый",
            "quantity": 20.0,
            "unit": "шт",
            "price": 45.50,
            "sum": None  # Отсутствует сумма
        }
    ]
}

# Накладная с множественными проблемами
INVOICE_MULTIPLE_ISSUES = {
    "supplier": "",  # Отсутствует поставщик
    "date": "invalid-date",  # Неверный формат даты
    "number": "129-Ж",
    "positions": [
        {
            "name": "Несуществующий товар",
            "quantity": -1.0,
            "unit": "invalid",
            "price": 100.00,
            "sum": 150.00
        },
        {
            "name": "",  # Отсутствует название
            "quantity": None,
            "unit": "",
            "price": None,
            "sum": None
        }
    ],
    "parser_comment": "Множественные проблемы в накладной"
}

# Накладная с очень длинными значениями
INVOICE_LONG_VALUES = {
    "supplier": "Очень длинное название поставщика " * 5,
    "date": "2024-03-15",
    "number": "130-" + "Z" * 50,
    "positions": [
        {
            "name": "Очень длинное название товара " * 5,
            "quantity": 1.0,
            "unit": "очень длинная единица измерения",
            "price": 100.00,
            "sum": 100.00
        }
    ],
    "parser_comment": "Очень длинный комментарий " * 20
}

# Словарь всех тестовых накладных
TEST_INVOICES = {
    "ok": INVOICE_OK,
    "qty_mismatch": INVOICE_QTY_MISMATCH,
    "not_found": INVOICE_NOT_FOUND,
    "empty": INVOICE_EMPTY,
    "unit_mismatch": INVOICE_UNIT_MISMATCH,
    "sum_mismatch": INVOICE_SUM_MISMATCH,
    "multiple_issues": INVOICE_MULTIPLE_ISSUES,
    "long_values": INVOICE_LONG_VALUES
}

# Тестовые проблемы для каждой накладной
TEST_ISSUES = {
    "ok": [],
    "qty_mismatch": [
        {
            "type": "position_no_quantity",
            "message": "❌ Позиция 1: не указано количество",
            "index": 1
        },
        {
            "type": "position_no_quantity",
            "message": "❌ Позиция 2: не указано количество",
            "index": 2
        }
    ],
    "not_found": [
        {
            "type": "product_not_found",
            "message": "❓ Позиция 1: товар не найден: Несуществующий товар",
            "index": 1
        },
        {
            "type": "product_not_found",
            "message": "❓ Позиция 2: товар не найден: Еще один неизвестный",
            "index": 2
        }
    ],
    "empty": [],
    "unit_mismatch": [
        {
            "type": "unit_mismatch",
            "message": "⚠️ Позиция 1: несовместимые единицы измерения: кг vs л",
            "index": 1
        },
        {
            "type": "position_no_unit",
            "message": "❌ Позиция 2: не указаны единицы измерения",
            "index": 2
        }
    ],
    "sum_mismatch": [
        {
            "type": "sum_mismatch",
            "message": "⚠️ Позиция 1: сумма позиции (899.00) не совпадает с общей суммой (1000.00)",
            "index": 1
        },
        {
            "type": "sum_mismatch",
            "message": "⚠️ Позиция 2: не указана сумма",
            "index": 2
        }
    ],
    "multiple_issues": [
        {
            "type": "supplier_missing",
            "message": "❌ Не указан поставщик"
        },
        {
            "type": "product_not_found",
            "message": "❓ Позиция 1: товар не найден: Несуществующий товар",
            "index": 1
        },
        {
            "type": "position_no_quantity",
            "message": "❌ Позиция 1: не указано количество",
            "index": 1
        },
        {
            "type": "unit_mismatch",
            "message": "⚠️ Позиция 1: несовместимые единицы измерения: invalid vs л",
            "index": 1
        },
        {
            "type": "position_no_name",
            "message": "❌ Позиция 2: не указано название",
            "index": 2
        }
    ],
    "long_values": []
} 