"""
Утилиты для модуля issue_editor.

Этот модуль содержит вспомогательные функции для работы с issue_editor.
"""

import re
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.sql import func
import structlog

from app.models.product import Product
from app.models.product_name_lookup import ProductNameLookup
from app.config.issue_editor_constants import SEMIFINISHED_PATTERNS

logger = structlog.get_logger()

def clean_name_for_comparison(name: str) -> str:
    """
    Подготавливает строку названия для сравнения:
    - Приводит к нижнему регистру
    - Убирает лишние пробелы
    - Убирает знаки пунктуации
    
    Args:
        name: Исходное название товара
        
    Returns:
        Очищенное название для сравнения
    """
    if not name:
        return ""
    
    # Приводим к нижнему регистру
    name = name.lower()
    
    # Удаляем лишние пробелы
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Удаляем или заменяем знаки пунктуации
    name = re.sub(r'[.,;:\-_()]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def is_semifinished(name: str) -> bool:
    """
    Проверяет, является ли товар полуфабрикатом по маркерам в названии.
    
    Args:
        name: название товара
        
    Returns:
        True если это полуфабрикат, иначе False
    """
    name_lower = name.lower()
    return any(re.search(pattern, name_lower) for pattern in SEMIFINISHED_PATTERNS)

async def get_products_by_name(
    session: AsyncSession, 
    name_query: str, 
    limit: int = 3,
    threshold: float = 0.7,
    exclude_semifinished: bool = True
) -> List[Dict[str, Any]]:
    """
    Ищет товары по части имени с учетом полуфабрикатов.
    
    Args:
        session: асинхронная сессия SQLAlchemy
        name_query: строка поиска
        limit: максимальное количество результатов
        threshold: минимальный порог схожести
        exclude_semifinished: исключить полуфабрикаты из результатов
        
    Returns:
        список товаров с их характеристиками
    """
    if not name_query:
        return []
    
    # Нормализуем запрос
    normalized_query = clean_name_for_comparison(name_query)
    
    # Пытаемся использовать функцию find_similar_products из fuzzy_match
    try:
        from app.routers.fuzzy_match import find_similar_products
        products = await find_similar_products(
            session, 
            normalized_query, 
            limit=limit, 
            threshold=threshold
        )
        
        # Фильтруем полуфабрикаты если нужно
        if exclude_semifinished:
            products = [p for p in products if not is_semifinished(p["name"])]
        
        return products
    except ImportError:
        logger.warning("fuzzy_match module not found, using fallback search")
    
    # Резервный путь: используем прямой SQL запрос
    stmt = (
        select(Product.id, Product.name, Product.unit)
        .where(func.lower(Product.name).like(f"%{normalized_query}%"))
        .order_by(Product.name)
        .limit(limit * 2)  # Запрашиваем больше для фильтрации
    )
    
    result = await session.execute(stmt)
    products = []
    
    for row in result:
        product = {
            "id": row.id,
            "name": row.name,
            "unit": row.unit,
            "confidence": 1.0  # Для прямого поиска считаем уверенность максимальной
        }
        
        if not exclude_semifinished or not is_semifinished(product["name"]):
            products.append(product)
    
    return products[:limit]

async def save_product_match(
    session: AsyncSession, 
    parsed_name: str, 
    product_id: int
) -> bool:
    """
    Сохраняет сопоставление названия товара с ID для будущего использования.
    
    Args:
        session: асинхронная сессия SQLAlchemy
        parsed_name: распознанное название товара
        product_id: ID товара в базе данных
        
    Returns:
        True если успешно, иначе False
    """
    if not parsed_name or not product_id:
        return False
    
    try:
        # Проверяем существование товара
        res = await session.execute(
            select(Product.id).where(Product.id == product_id)
        )
        if not res.scalar_one_or_none():
            logger.warning("Cannot add lookup entry - product does not exist", 
                          product_id=product_id)
            return False
        
        # Проверяем, нет ли уже такого сопоставления
        res = await session.execute(
            select(ProductNameLookup.id).where(
                ProductNameLookup.alias == parsed_name
            )
        )
        existing_id = res.scalar_one_or_none()
        
        if existing_id:
            # Обновляем существующую запись
            await session.execute(
                update(ProductNameLookup)
                .where(ProductNameLookup.id == existing_id)
                .values(product_id=product_id)
            )
        else:
            # Создаем новую запись
            await session.execute(
                insert(ProductNameLookup).values(
                    alias=parsed_name,
                    product_id=product_id
                )
            )
        
        await session.commit()
        return True
        
    except Exception as e:
        logger.error("Failed to save product match", 
                    error=str(e),
                    parsed_name=parsed_name,
                    product_id=product_id)
        await session.rollback()
        return False 