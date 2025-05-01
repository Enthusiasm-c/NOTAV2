"""
Модуль для нечеткого поиска товаров по названию в CSV-файлах.

Использует RapidFuzz для поиска товаров, наиболее похожих на введенное название.
"""

from __future__ import annotations

import structlog
from typing import List, Tuple, Dict, Any, Optional

from rapidfuzz import fuzz, process

from app.core.data_loader import get_product_alias, PRODUCTS

logger = structlog.get_logger()

# Минимальный порог схожести для включения в результаты
DEFAULT_THRESHOLD = 0.7

# Максимальное количество возвращаемых похожих товаров
MAX_SIMILAR_PRODUCTS = 3


async def fuzzy_match_product(
    name: str, 
    threshold: Optional[float] = None
) -> Tuple[Optional[int], float]:
    """
    Находит наиболее подходящий товар с помощью нечеткого поиска.
    
    Args:
        name: Название товара для поиска
        threshold: Порог схожести, ниже которого товары игнорируются
    
    Returns:
        Tuple[id товара или None, степень схожести]
    """
    if not name:
        return None, 0.0
    
    if threshold is None:
        threshold = DEFAULT_THRESHOLD
    
    # Сначала пытаемся найти точное совпадение
    product = get_product_alias(name)
    if product:
        logger.info("Product found by exact match", 
                   name=name, product_id=product["id"])
        return product["id"], 1.0
    
    # Если точного совпадения нет, используем нечеткий поиск
    try:
        # Создаем словарь для поиска
        choices = {str(p["id"]): p["name"] for p in PRODUCTS.to_dict("records")}
        
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
                product_id = int(pid)
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
    name: str, 
    limit: int = MAX_SIMILAR_PRODUCTS,
    threshold: float = DEFAULT_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Находит список похожих товаров.
    
    Args:
        name: Название товара для поиска
        limit: Максимальное количество результатов
        threshold: Минимальный порог схожести
    
    Returns:
        Список словарей с информацией о похожих товарах
    """
    if not name:
        return []
    
    # Создаем словарь для поиска
    products_list = PRODUCTS.to_dict("records")
    product_dict = {p["id"]: p for p in products_list}
    choices = {p["id"]: p["name"] for p in products_list}
    
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
                "id": product["id"],
                "name": product["name"],
                "unit": product["measureName"],
                "confidence": normalized_score
            })
        
        return result_products
        
    except Exception as e:
        logger.error("Error finding similar products", error=str(e))
        return []
