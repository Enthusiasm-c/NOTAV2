"""Утилиты для тестов."""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.product import Product
from app.models.product_name_lookup import ProductNameLookup
from app.models.supplier import Supplier


async def create_test_supplier(
    session: AsyncSession,
    name: str = "ООО Тест",
    inn: str = "1234567890",
    kpp: str = "123456789",
    address: str = "г. Москва, ул. Тестовая, д. 1",
    phone: str = "+7 (999) 123-45-67",
    email: str = "test@example.com",
    comment: str = "Тестовый поставщик",
) -> Supplier:
    """Создает тестового поставщика.

    Args:
        session: Сессия базы данных
        name: Название поставщика
        inn: ИНН
        kpp: КПП
        address: Адрес
        phone: Телефон
        email: Email
        comment: Комментарий

    Returns:
        Supplier: Созданный поставщик
    """
    supplier = Supplier(
        name=name,
        inn=inn,
        kpp=kpp,
        address=address,
        phone=phone,
        email=email,
        comment=comment,
    )
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def create_test_product(
    session: AsyncSession,
    name: str = "Тестовый продукт",
    code: str = "TP",
    unit: str = "шт",
    price: float = 100.0,
    comment: str = "Тестовый продукт",
) -> Product:
    """Создает тестовый продукт.

    Args:
        session: Сессия базы данных
        name: Название продукта
        code: Код продукта
        unit: Единица измерения
        price: Цена
        comment: Комментарий

    Returns:
        Product: Созданный продукт
    """
    product = Product(
        name=name,
        code=code,
        unit=unit,
        price=price,
        comment=comment,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def create_test_product_alias(
    session: AsyncSession,
    alias: str = "тест",
    product_id: int = 1,
    comment: str = "Тестовый алиас",
) -> ProductNameLookup:
    """Создает тестовый алиас продукта.

    Args:
        session: Сессия базы данных
        alias: Алиас
        product_id: ID продукта
        comment: Комментарий

    Returns:
        ProductNameLookup: Созданный алиас
    """
    product_alias = ProductNameLookup(
        alias=alias,
        product_id=product_id,
        comment=comment,
    )
    session.add(product_alias)
    await session.commit()
    await session.refresh(product_alias)
    return product_alias


async def create_test_invoice(
    session: AsyncSession,
    number: str = "INV-001",
    date: str = "2024-01-01",
    supplier_id: int = 1,
    comment: str = "Тестовая накладная",
) -> Invoice:
    """Создает тестовую накладную.

    Args:
        session: Сессия базы данных
        number: Номер накладной
        date: Дата накладной
        supplier_id: ID поставщика
        comment: Комментарий

    Returns:
        Invoice: Созданная накладная
    """
    invoice = Invoice(
        number=number,
        date=date,
        supplier_id=supplier_id,
        comment=comment,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def create_test_invoice_item(
    session: AsyncSession,
    invoice_id: int = 1,
    product_id: int = 1,
    name: str = "Тестовый продукт",
    quantity: float = 10,
    unit: str = "шт",
    price: float = 100.0,
    comment: str = "Тестовая позиция",
) -> InvoiceItem:
    """Создает тестовую позицию накладной.

    Args:
        session: Сессия базы данных
        invoice_id: ID накладной
        product_id: ID продукта
        name: Название продукта
        quantity: Количество
        unit: Единица измерения
        price: Цена
        comment: Комментарий

    Returns:
        InvoiceItem: Созданная позиция
    """
    invoice_item = InvoiceItem(
        invoice_id=invoice_id,
        product_id=product_id,
        name=name,
        quantity=quantity,
        unit=unit,
        price=price,
        comment=comment,
    )
    session.add(invoice_item)
    await session.commit()
    await session.refresh(invoice_item)
    return invoice_item


async def create_test_data(session: AsyncSession) -> Dict[str, List[Any]]:
    """Создает тестовые данные.

    Args:
        session: Сессия базы данных

    Returns:
        Dict[str, List[Any]]: Словарь с созданными данными
    """
    suppliers = []
    for supplier_data in TEST_SUPPLIERS:
        supplier = await create_test_supplier(
            session,
            name=supplier_data.name,
            inn=supplier_data.inn,
            kpp=supplier_data.kpp,
            address=supplier_data.address,
            phone=supplier_data.phone,
            email=supplier_data.email,
            comment=supplier_data.comment,
        )
        suppliers.append(supplier)

    products = []
    for product_data in TEST_PRODUCTS:
        product = await create_test_product(
            session,
            name=product_data.name,
            code=product_data.code,
            unit=product_data.unit,
            price=product_data.price,
            comment=product_data.comment,
        )
        products.append(product)

    product_aliases = []
    for alias_data in TEST_PRODUCT_ALIASES:
        product_alias = await create_test_product_alias(
            session,
            alias=alias_data.alias,
            product_id=alias_data.product_id,
            comment=alias_data.comment,
        )
        product_aliases.append(product_alias)

    invoices = []
    for invoice_data in TEST_INVOICES:
        invoice = await create_test_invoice(
            session,
            number=invoice_data.number,
            date=invoice_data.date,
            supplier_id=invoice_data.supplier_id,
            comment=invoice_data.comment,
        )
        invoices.append(invoice)

    invoice_items = []
    for item_data in TEST_INVOICE_ITEMS:
        invoice_item = await create_test_invoice_item(
            session,
            invoice_id=item_data.invoice_id,
            product_id=item_data.product_id,
            name=item_data.name,
            quantity=item_data.quantity,
            unit=item_data.unit,
            price=item_data.price,
            comment=item_data.comment,
        )
        invoice_items.append(invoice_item)

    return {
        "suppliers": suppliers,
        "products": products,
        "product_aliases": product_aliases,
        "invoices": invoices,
        "invoice_items": invoice_items,
    } 