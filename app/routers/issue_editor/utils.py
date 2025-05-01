"""
Утилиты для редактора проблем.

Этот модуль содержит функции для работы с данными в CSV формате.
"""

import structlog
from typing import List, Dict, Any, Optional
import pandas as pd

from app.core.data_loader import PRODUCTS, load_data
from app.routers.fuzzy_match import find_similar_products

logger = structlog.get_logger()

async def get_products_by_name(name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Поиск товаров по названию.
    
    Args:
        name: Название для поиска
        limit: Максимальное количество результатов
        
    Returns:
        List[Dict[str, Any]]: Список найденных товаров
    """
    if not name:
        return []
        
    # Используем find_similar_products для поиска
    products = await find_similar_products(name, limit=limit)
    
    # Преобразуем результаты в нужный формат
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "unit": p["unit"],
            "confidence": p["confidence"]
        }
        for p in products
    ]

async def save_product_match(
    product_id: int,
    original_name: str,
    confidence: float
) -> bool:
    """
    Сохраняет сопоставление товара в CSV.
    
    Args:
        product_id: ID товара в справочнике
        original_name: Исходное название из накладной
        confidence: Уверенность в сопоставлении
        
    Returns:
        bool: True если сохранение успешно
    """
    try:
        # Получаем информацию о товаре
        if PRODUCTS is None:
            load_data()
            
        product_mask = PRODUCTS["id"] == product_id
        if not product_mask.any():
            logger.error("Product not found", product_id=product_id)
            return False
            
        product = PRODUCTS[product_mask].iloc[0]
        
        # Создаем новую запись для learned_products.csv
        new_match = pd.DataFrame([{
            "original_name": original_name,
            "product_id": product_id,
            "product_name": product["name"],
            "confidence": confidence,
            "is_verified": True
        }])
        
        # Добавляем в CSV
        csv_path = "data/learned_products.csv"
        try:
            existing = pd.read_csv(csv_path)
            # Проверяем, нет ли уже такого сопоставления
            mask = existing["original_name"] == original_name
            if mask.any():
                # Обновляем существующую запись
                existing.loc[mask] = new_match.iloc[0]
                existing.to_csv(csv_path, index=False)
            else:
                # Добавляем новую запись
                pd.concat([existing, new_match]).to_csv(csv_path, index=False)
        except FileNotFoundError:
            # Создаем новый файл
            new_match.to_csv(csv_path, index=False)
            
        logger.info(
            "Product match saved",
            original_name=original_name,
            product_id=product_id,
            confidence=confidence
        )
        return True
        
    except Exception as e:
        logger.exception(
            "Failed to save product match",
            error=str(e),
            original_name=original_name,
            product_id=product_id
        )
        return False 