"""
Модуль для нечеткого поиска товаров по названию в базе данных.

Использует RapidFuzz для поиска товаров, наиболее похожих на введенное название.
"""

from __future__ import annotations

import structlog
from typing import List, Tuple, Dict, Any, Optional

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.product import Product
from app.models.product_name_lookup import ProductNameLookup

logger = structlog.get_logger()

# Минимальный порог схожести для включения в результаты
DEFAULT_THRESHOLD = 0.7

# Максимальное количество возвращаемых похожих товаров
MAX_SIMILAR_PRODUCTS = 3


async def fuzzy_match_product(
    session: AsyncSession, 
    name: str, 
    threshold: Optional[float] = None
) -> Tuple[Optional[int], float]:
    """
    Находит наиболее подходящий товар в базе данных с помощью нечеткого поиска.
    
    Args:
        session: Асинхронная сессия SQLAlchemy
        name: Название товара для поиска
        threshold: Порог схожести, ниже которого товары игнорируются
    
    Returns:
        Tuple[id товара или None, степень схожести]
    """
    if not name:
        return None, 0.0
    
    if threshold is None:
        threshold = DEFAULT_THRESHOLD
    
    # Сначала пытаемся найти в lookup таблице
    stmt = select(ProductNameLookup).where(ProductNameLookup.alias == name)
    result = await session.execute(stmt)
    lookup = result.scalar_one_or_none()
    
    if lookup:
        logger.info("Product found in lookup table", 
                   name=name, product_id=lookup.product_id)
        return lookup.product_id, 1.0  # Точное совпадение
    
    # Загружаем все товары
    stmt = select(Product)
    result = await session.execute(stmt)
    products = result.scalars().all()
    
    if not products:
        return None, 0.0
    
    # Создаем словарь для поиска
    choices = {p.id: p.name for p in products}
    
    try:
        # Выполняем нечеткий поиск
        matches = process.extract(
            name, 
            choices=choices.values(),
            scorer=fuzz.token_sort_ratio, 
            limit=MAX_SIMILAR_PRODUCTS
        )
        
        if not matches:
            return None, 0.0
            
        # В зависимости от версии RapidFuzz, формат возвращаемых данных может отличаться
        # Более новые версии возвращают (match, score, index), более старые - (match, score)
        if len(matches[0]) == 3:  # формат (match, score, index)
            best_match, best_score, _ = matches[0]
        elif len(matches[0]) == 2:  # формат (match, score)
            best_match, best_score = matches[0]
        else:
            logger.error("Unexpected format from rapidfuzz", match_format=matches[0])
            return None, 0.0
        
        normalized_score = best_score / 100.0  # Нормализуем до диапазона 0-1
        
        if normalized_score < threshold:
            logger.debug("No matching product above threshold", 
                        name=name, best_match=best_match, score=normalized_score)
            return None, normalized_score
        
        # Находим ID товара по его имени
        product_id = None
        for pid, pname in choices.items():
            if pname == best_match:
                product_id = pid
                break
        
        logger.info("Fuzzy matching product found", 
                   name=name, 
                   match=best_match, 
                   score=normalized_score,
                   product_id=product_id)
        
        return product_id, normalized_score
        
    except Exception as e:
        logger.error("Error during fuzzy matching", error=str(e))
        return None, 0.0


async def find_similar_products(
    session: AsyncSession, 
    name: str, 
    limit: int = MAX_SIMILAR_PRODUCTS,
    threshold: float = DEFAULT_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Находит список похожих товаров в базе данных.
    
    Args:
        session: Асинхронная сессия SQLAlchemy
        name: Название товара для поиска
        limit: Максимальное количество результатов
        threshold: Минимальный порог схожести
    
    Returns:
        Список словарей с информацией о похожих товарах
    """
    if not name:
        return []
    
    # Загружаем все товары
    stmt = select(Product)
    result = await session.execute(stmt)
    products = result.scalars().all()
    
    if not products:
        return []
    
    # Создаем словарь для поиска
    product_dict = {p.id: p for p in products}
    choices = {p.id: p.name for p in products}
    
    try:
        # Выполняем нечеткий поиск
        matches = process.extract(
            name, 
            choices=choices.values(),
            scorer=fuzz.token_sort_ratio, 
            limit=limit
        )
        
        # Фильтруем по порогу и создаем результат
        result_products = []
        
        for match_data in matches:
            # Обрабатываем разные форматы результата
            if len(match_data) == 3:  # формат (match, score, index)
                match_name, score, _ = match_data
            elif len(match_data) == 2:  # формат (match, score)
                match_name, score = match_data
            else:
                logger.error("Unexpected format from rapidfuzz", match_format=match_data)
                continue
                
            normalized_score = score / 100.0
            
            if normalized_score < threshold:
                continue
            
            # Находим товар по имени
            product_id = None
            for pid, pname in choices.items():
                if pname == match_name:
                    product_id = pid
                    break
            
            if product_id is None:
                continue
            
            product = product_dict[product_id]
            
            result_products.append({
                "id": product.id,
                "name": product.name,
                "unit": product.unit,
                "confidence": normalized_score
            })
        
        # Сортируем по убыванию уверенности
        result_products.sort(key=lambda p: p["confidence"], reverse=True)
        
        return result_products
    except Exception as e:
        logger.error("Error finding similar products", error=str(e))
        return []
