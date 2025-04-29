"""
Модуль для управления сопоставлениями названий товаров (самообучение).
Позволяет запоминать связи между распознанными названиями и товарами из БД.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple
import structlog

from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_name_lookup import ProductNameLookup
from app.models.product import Product

logger = structlog.get_logger()


async def add_lookup_entry(
    session: AsyncSession,
    parsed_name: str,
    product_id: int,
    confidence: float = 1.0
) -> bool:
    """
    Добавляет новое сопоставление в таблицу lookup.
    
    :param session: асинхронная сессия SQLAlchemy
    :param parsed_name: распознанное название из накладной
    :param product_id: ID товара в базе данных
    :param confidence: уверенность в сопоставлении (0-1)
    :return: True если успешно, иначе False
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
            # Обновляем существующее сопоставление
            await session.execute(
                update(ProductNameLookup)
                .where(ProductNameLookup.id == existing_id)
                .values(product_id=product_id)
            )
            logger.info("Updated existing lookup entry", 
                       lookup_id=existing_id, 
                       parsed_name=parsed_name, 
                       product_id=product_id)
        else:
            # Создаем новое сопоставление
            stmt = insert(ProductNameLookup).values(
                alias=parsed_name,
                product_id=product_id
            )
            await session.execute(stmt)
            logger.info("Added new lookup entry", 
                       parsed_name=parsed_name, 
                       product_id=product_id)
        
        # Коммитим изменения
        await session.commit()
        return True
    
    except Exception as e:
        await session.rollback()
        logger.error("Failed to add lookup entry", 
                    error=str(e), 
                    parsed_name=parsed_name, 
                    product_id=product_id)
        return False


async def remove_lookup_entry(
    session: AsyncSession, 
    parsed_name: str
) -> bool:
    """
    Удаляет сопоставление из таблицы lookup.
    
    :param session: асинхронная сессия SQLAlchemy
    :param parsed_name: распознанное название из накладной
    :return: True если успешно, иначе False
    """
    try:
        stmt = delete(ProductNameLookup).where(
            ProductNameLookup.alias == parsed_name
        )
        result = await session.execute(stmt)
        await session.commit()
        
        if result.rowcount > 0:
            logger.info("Removed lookup entry", parsed_name=parsed_name)
            return True
        else:
            logger.warning("Lookup entry not found", parsed_name=parsed_name)
            return False
    
    except Exception as e:
        await session.rollback()
        logger.error("Failed to remove lookup entry", 
                    error=str(e), 
                    parsed_name=parsed_name)
        return False


async def get_lookup_statistics(session: AsyncSession) -> Dict[str, int]:
    """
    Получает статистику по таблице lookup.
    
    :param session: асинхронная сессия SQLAlchemy
    :return: словарь со статистикой
    """
    try:
        # Общее количество записей
        res = await session.execute(
            select(ProductNameLookup.id)
        )
        total_count = len(res.all())
        
        # Количество уникальных товаров
        res = await session.execute(
            select(ProductNameLookup.product_id).distinct()
        )
        unique_products = len(res.all())
        
        return {
            "total_entries": total_count,
            "unique_products": unique_products
        }
    
    except Exception as e:
        logger.error("Failed to get lookup statistics", error=str(e))
        return {
            "total_entries": 0,
            "unique_products": 0,
            "error": str(e)
        }


async def process_fixed_issues(
    session: AsyncSession,
    fixed_issues: Dict[int, Dict[str, Any]],
    invoice_data: Dict[str, Any]
) -> None:
    """
    Обрабатывает исправленные позиции и обновляет таблицу lookup.
    
    :param session: асинхронная сессия SQLAlchemy
    :param fixed_issues: словарь исправленных позиций
    :param invoice_data: данные накладной
    """
    if not fixed_issues or not invoice_data or "positions" not in invoice_data:
        return
    
    positions = invoice_data.get("positions", [])
    
    for position_idx, fix_data in fixed_issues.items():
        if position_idx >= len(positions):
            continue
        
        position = positions[position_idx]
        original_name = position.get("name")
        
        if not original_name:
            continue
        
        action = fix_data.get("action")
        
        # Если позиция была удалена, пропускаем
        if action == "delete" or position.get("deleted", False):
            continue
        
        # Если был выбран товар из базы
        if action == "replace_product" and "product_id" in fix_data:
            product_id = fix_data["product_id"]
            await add_lookup_entry(session, original_name, product_id)
            
            # Если также изменилась единица измерения
            if "old_unit" in fix_data and "new_unit" in fix_data:
                # Сохраняем составное название с единицей
                combined_name = f"{original_name} {fix_data['old_unit']}"
                await add_lookup_entry(session, combined_name, product_id)
