"""Тесты для модели ProductNameLookup."""
import pytest
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product_name_lookup import ProductNameLookup
from app.models.product import Product

@pytest.mark.asyncio
async def test_product_name_lookup_creation(test_product_name_lookup):
    """Тест создания записи поиска по названию товара."""
    assert test_product_name_lookup.alias == "тестовый товар"
    assert test_product_name_lookup.comment == "Тестовый комментарий"

@pytest.mark.asyncio
async def test_product_name_lookup_string_representation(test_product_name_lookup):
    """Тест строкового представления записи поиска."""
    expected = f"{test_product_name_lookup.alias} -> {test_product_name_lookup.product.name}"
    assert str(test_product_name_lookup) == expected

@pytest.mark.asyncio
async def test_product_name_lookup_product_relationship(test_product_name_lookup, test_product):
    """Тест связи записи поиска с товаром."""
    assert test_product_name_lookup.product_id == test_product.id
    assert test_product_name_lookup.product.name == "Тестовый товар"
    assert test_product_name_lookup.product.code == "TEST001"
    assert test_product_name_lookup.product.unit == "шт"

@pytest.mark.asyncio
async def test_product_name_lookup_validation(test_db, test_product):
    """Тест валидации данных записи поиска."""
    # Тест с некорректным алиасом
    with pytest.raises(ValueError):
        lookup = ProductNameLookup(
            alias="",  # Пустой алиас
            product_id=test_product.id
        )
        test_db.add(lookup)
        await test_db.commit()

    # Тест с отсутствующим товаром
    with pytest.raises(ValueError):
        lookup = ProductNameLookup(
            alias="тестовый товар",
            product_id=None  # Отсутствующий товар
        )
        test_db.add(lookup)
        await test_db.commit()

@pytest.mark.asyncio
async def test_product_name_lookup_unique_alias(test_db, test_product):
    """Тест уникальности алиаса в записях поиска."""
    # Пытаемся создать запись с существующим алиасом
    duplicate_lookup = ProductNameLookup(
        alias="тестовый товар",  # Используем существующий алиас
        product_id=test_product.id
    )
    test_db.add(duplicate_lookup)
    with pytest.raises(Exception):  # Ожидаем ошибку уникальности
        await test_db.commit()

@pytest.mark.asyncio
async def test_product_name_lookup_case_insensitive(test_db, test_product):
    """Тест регистронезависимого поиска по алиасу."""
    # Создаем запись с алиасом в верхнем регистре
    lookup = ProductNameLookup(
        alias="ТЕСТОВЫЙ ТОВАР",
        product_id=test_product.id
    )
    test_db.add(lookup)
    await test_db.commit()
    
    # Проверяем, что поиск работает независимо от регистра
    result = await test_db.query(ProductNameLookup).filter(
        ProductNameLookup.alias.ilike("тестовый товар")
    ).first()
    assert result is not None
    assert result.alias == "ТЕСТОВЫЙ ТОВАР"

@pytest.mark.asyncio
async def test_product_name_lookup_alias_length(test_db, test_product):
    """Тест длины алиаса."""
    # Тест с алиасом, превышающим максимальную длину
    with pytest.raises(ValueError):
        lookup = ProductNameLookup(
            alias="a" * 256,  # Алиас длиннее 255 символов
            product_id=test_product.id
        )
        test_db.add(lookup)
        await test_db.commit()

@pytest.mark.asyncio
async def test_product_name_lookup_alias_format(test_db, test_product):
    """Тест формата алиаса."""
    # Тест с алиасом, содержащим недопустимые символы
    with pytest.raises(ValueError):
        lookup = ProductNameLookup(
            alias="тест@товар",  # Алиас содержит недопустимый символ
            product_id=test_product.id
        )
        test_db.add(lookup)
        await test_db.commit()

@pytest.mark.asyncio
async def test_product_name_lookup_comment_length(test_db, test_product):
    """Тест длины комментария."""
    # Тест с комментарием, превышающим максимальную длину
    with pytest.raises(ValueError):
        lookup = ProductNameLookup(
            alias="тестовый товар",
            product_id=test_product.id,
            comment="c" * 1001  # Комментарий длиннее 1000 символов
        )
        test_db.add(lookup)
        await test_db.commit()

@pytest.mark.asyncio
async def test_product_name_lookup_update(test_db, test_product_name_lookup):
    """Тест обновления записи поиска."""
    # Обновляем данные записи
    test_product_name_lookup.alias = "новый алиас"
    test_product_name_lookup.comment = "Новый комментарий"
    await test_db.commit()
    await test_db.refresh(test_product_name_lookup)

    # Проверяем обновленные данные
    assert test_product_name_lookup.alias == "новый алиас"
    assert test_product_name_lookup.comment == "Новый комментарий"

@pytest.mark.asyncio
async def test_product_name_lookup_fuzzy_search(test_db, test_product):
    """Тест нечеткого поиска по алиасу."""
    # Создаем записи с похожими алиасами
    lookups = [
        ProductNameLookup(alias="тестовый товар", product_id=test_product.id),
        ProductNameLookup(alias="тестовый товар 2", product_id=test_product.id),
        ProductNameLookup(alias="тестовый товар 3", product_id=test_product.id)
    ]
    for lookup in lookups:
        test_db.add(lookup)
    await test_db.commit()

    # Проверяем поиск с опечаткой
    result = await test_db.query(ProductNameLookup).filter(
        ProductNameLookup.alias.ilike("%тестовый%товар%")
    ).all()
    assert len(result) == 3

@pytest.mark.asyncio
async def test_product_name_lookup_cascade_delete(test_db, test_product, test_product_name_lookup):
    """Тест каскадного удаления записей поиска при удалении товара."""
    product_id = test_product.id
    lookup_id = test_product_name_lookup.id
    
    # Удаляем товар
    await test_db.delete(test_product)
    await test_db.commit()
    
    # Проверяем, что товар удален
    deleted_product = await test_db.get(Product, product_id)
    assert deleted_product is None
    
    # Проверяем, что запись поиска также удалена
    deleted_lookup = await test_db.get(ProductNameLookup, lookup_id)
    assert deleted_lookup is None

@pytest.mark.asyncio
async def test_product_name_lookup_edge_cases(test_db, test_product):
    """Тест граничных случаев для записи поиска."""
    # Тест с минимально допустимым алиасом
    lookup = ProductNameLookup(
        alias="a",  # Минимальная длина алиаса
        product_id=test_product.id
    )
    test_db.add(lookup)
    await test_db.commit()
    assert lookup.alias == "a"

    # Тест с максимально допустимым алиасом
    lookup = ProductNameLookup(
        alias="a" * 255,  # Максимальная длина алиаса
        product_id=test_product.id
    )
    test_db.add(lookup)
    await test_db.commit()
    assert len(lookup.alias) == 255

@pytest.mark.asyncio
async def test_product_name_lookup_special_characters(test_db, test_product):
    """Тест обработки специальных символов в алиасе."""
    # Тест с пробелами в начале и конце
    lookup = ProductNameLookup(
        alias="  тестовый товар  ",  # Пробелы в начале и конце
        product_id=test_product.id
    )
    test_db.add(lookup)
    await test_db.commit()
    assert lookup.alias == "тестовый товар"  # Должны быть удалены лишние пробелы

    # Тест с множественными пробелами
    lookup = ProductNameLookup(
        alias="тестовый   товар",  # Множественные пробелы
        product_id=test_product.id
    )
    test_db.add(lookup)
    await test_db.commit()
    assert lookup.alias == "тестовый товар"  # Должны быть удалены лишние пробелы

@pytest.mark.asyncio
async def test_product_name_lookup_foreign_key_constraints(test_db: AsyncSession):
    """Тест ограничений внешних ключей."""
    # Создаем тестовый товар
    product = Product(
        name="Тестовый товар",
        code="TEST_FK_001",
        unit="шт",
        price=Decimal("100.50")
    )
    test_db.add(product)
    await test_db.commit()
    
    # Тест с несуществующим товаром
    with pytest.raises(IntegrityError):
        lookup = ProductNameLookup(
            alias="тестовый товар",
            product_id=999999  # Несуществующий ID товара
        )
        test_db.add(lookup)
        await test_db.commit()
    await test_db.rollback()
    
    # Тест с существующим товаром (должен пройти)
    lookup = ProductNameLookup(
        alias="тестовый товар",
        product_id=product.id
    )
    test_db.add(lookup)
    await test_db.commit()
    
    # Проверяем каскадное удаление
    await test_db.delete(product)
    await test_db.commit()
    
    # Проверяем, что lookup тоже удален
    result = await test_db.execute(
        select(ProductNameLookup).where(ProductNameLookup.product_id == product.id)
    )
    assert result.first() is None

@pytest.mark.asyncio
async def test_product_name_lookup_duplicate_aliases_different_products(
    test_db, test_product
):
    """Тест дублирования алиасов для разных товаров."""
    # Создаем второй товар
    product2 = Product(
        name="Тестовый товар 2",
        code="TEST002",
        unit="шт",
        price=Decimal("200.00")
    )
    test_db.add(product2)
    await test_db.commit()

    # Создаем запись поиска с тем же алиасом для второго товара
    lookup2 = ProductNameLookup(
        alias="тестовый товар",  # Тот же алиас
        product_id=product2.id
    )
    test_db.add(lookup2)
    await test_db.commit()

    # Проверяем, что обе записи существуют
    lookups = await test_db.query(ProductNameLookup).filter(
        ProductNameLookup.alias == "тестовый товар"
    ).all()
    assert len(lookups) == 2
    assert {l.product_id for l in lookups} == {test_product.id, product2.id}

@pytest.mark.asyncio
async def test_product_name_lookup_case_sensitive_unique(test_db, test_product):
    """Тест регистрозависимой уникальности алиасов."""
    # Создаем запись с алиасом в другом регистре
    lookup = ProductNameLookup(
        alias="ТЕСТОВЫЙ ТОВАР",  # Алиас в верхнем регистре
        product_id=test_product.id
    )
    test_db.add(lookup)
    await test_db.commit()

    # Проверяем, что можно создать запись с тем же алиасом в другом регистре
    lookup2 = ProductNameLookup(
        alias="тестовый товар",  # Алиас в нижнем регистре
        product_id=test_product.id
    )
    test_db.add(lookup2)
    with pytest.raises(Exception):  # Ожидаем ошибку уникальности
        await test_db.commit() 