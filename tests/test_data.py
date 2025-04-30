"""Тестовые данные для тестов."""

from datetime import date
from decimal import Decimal

from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.product import Product
from app.models.product_name_lookup import ProductNameLookup
from app.models.supplier import Supplier

# Тестовые поставщики
TEST_SUPPLIERS = [
    {
        "name": "ООО Тестовая Компания",
        "inn": "1234567890",
        "kpp": "123456789",
        "address": "г. Москва, ул. Тестовая, д. 1",
        "phone": "+7 (999) 123-45-67",
        "email": "test@example.com",
        "comment": "Тестовый поставщик 1"
    },
    {
        "name": "ИП Иванов И.И.",
        "inn": "0987654321",
        "kpp": "987654321",
        "address": "г. Санкт-Петербург, пр. Тестовый, д. 2",
        "phone": "+7 (999) 765-43-21",
        "email": "ivanov@example.com",
        "comment": "Тестовый поставщик 2"
    }
]

# Тестовые продукты
TEST_PRODUCTS = [
    {
        "name": "Тестовый товар 1",
        "code": "TEST001",
        "unit": "шт",
        "price": Decimal("100.50"),
        "comment": "Тестовый товар 1"
    },
    {
        "name": "Тестовый товар 2",
        "code": "TEST002",
        "unit": "кг",
        "price": Decimal("200.75"),
        "comment": "Тестовый товар 2"
    }
]

# Тестовые алиасы продуктов
TEST_PRODUCT_ALIASES = [
    {
        "alias": "тестовый товар 1",
        "comment": "Алиас для тестового товара 1"
    },
    {
        "alias": "тестовый товар 2",
        "comment": "Алиас для тестового товара 2"
    }
]

# Тестовые накладные
TEST_INVOICES = [
    {
        "number": "TEST-001",
        "date": date(2024, 3, 20),
        "comment": "Тестовая накладная 1"
    },
    {
        "number": "TEST-002",
        "date": date(2024, 3, 21),
        "comment": "Тестовая накладная 2"
    }
]

# Тестовые позиции накладных
TEST_INVOICE_ITEMS = [
    {
        "name": "Тестовый товар 1",
        "quantity": Decimal("10"),
        "unit": "шт",
        "price": Decimal("100.50"),
        "comment": "Тестовая позиция 1"
    },
    {
        "name": "Тестовый товар 2",
        "quantity": Decimal("5"),
        "unit": "кг",
        "price": Decimal("200.75"),
        "comment": "Тестовая позиция 2"
    }
] 