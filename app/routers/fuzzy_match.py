"""
Усовершенствованный модуль нечеткого поиска товаров.

Улучшения:
1. Игнорирование регистра при поиске
2. Фильтрация полуфабрикатов (s/f) из предложений
3. Сохранение совпадений для будущего использования
4. Улучшенные алгоритмы сопоставления
"""

from __future__ import annotations

from typing import Tuple, Optional, List, Dict, Any
import re
import structlog

from rapidfuzz import fuzz, process
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.product_name_lookup import ProductNameLookup
from app.models.product import Product

logger = structlog.get_logger()

# Константы для настройки алгоритма
SEMIFINISHED_PATTERNS = [r's/f', r's/finished', r'semi.?finished', r'semi.?fabricated']
MIN_CONFIDENCE_FOR_LEARNING = 0.90  # Минимальная уверенность для автообучения

def clean_name_for_comparison(name: str) -> str:
    """
    Подготавливает строку названия для сравнения:
    - Приводит к нижнему регистру
    - Убирает лишние пробелы
    - Убирает знаки пунктуации
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
    
    :param name: название товара
    :return: True если это полуфабрикат, иначе False
    """
    name_lower = name.lower()
    return any(re.search(pattern, name_lower) for pattern in SEMIFINISHED_PATTERNS)


async def save_match_to_lookup(
    session: AsyncSession,
    parsed_name: str,
    product_id: int,
    confidence: float,
) -> None:
    """
    Сохраняет сопоставление в таблицу lookup для будущего использования.
    
    :param session: асинхронная сессия SQLAlchemy
    :param parsed_name: строка из OCR/Parsing
    :param product_id: ID сопоставленного товара
    :param confidence: уверенность совпадения (0-1)
    """
    if confidence < MIN_CONFIDENCE_FOR_LEARNING:
        return  # Не сохраняем сопоставления с низкой уверенностью
    
    # Проверяем, есть ли уже такое сопоставление
    res = await session.execute(
        select(ProductNameLookup.id)
        .where(ProductNameLookup.alias == parsed_name)
    )
    existing_id = res.scalar_one_or_none()
    
    try:
        if existing_id:
            # Обновляем существующее сопоставление
            await session.execute(
                update(ProductNameLookup)
                .where(ProductNameLookup.id == existing_id)
                .values(product_id=product_id)
            )
        else:
            # Создаем новое сопоставление
            await session.execute(
                insert(ProductNameLookup).values(
                    alias=parsed_name,
                    product_id=product_id,
                )
            )
        
        # Коммитим изменения
        await session.commit()
        logger.info("Saved match to lookup table", 
                   parsed_name=parsed_name, 
                   product_id=product_id, 
                   confidence=confidence)
    except Exception as e:
        await session.rollback()
        logger.error("Failed to save match to lookup table", 
                    error=str(e),
                    parsed_name=parsed_name,
                    product_id=product_id)


async def fuzzy_match_product(
    session: AsyncSession,
    parsed_name: str,
    threshold: float | None = None,
    exclude_semifinished: bool = True,
) -> Tuple[Optional[int], float]:
    """
    Улучшенный поиск товара по распознанному названию.
    
    :param session: асинхронная сессия SQLAlchemy
    :param parsed_name: строка из OCR/Parsing
    :param threshold: кастомный порог RapidFuzz (0–1); если None → settings
    :param exclude_semifinished: исключать ли полуфабрикаты из результатов
    :return: (product_id | None, confidence 0–1)
    """
    if not parsed_name:
        return None, 0.0
    
    threshold = threshold or settings.fuzzy_threshold
    
    # Нормализуем имя для поиска
    normalized_name = clean_name_for_comparison(parsed_name)
    
    # ───────────────────────── 1. lookup по памяти ────────────────────────
    # Сначала ищем по точному совпадению
    res = await session.execute(
        select(ProductNameLookup.product_id).where(
            ProductNameLookup.alias == parsed_name
        )
    )
    product_id = res.scalar_one_or_none()
    if product_id is not None:
        return product_id, 1.0
    
    # Затем ищем по нормализованному имени
    res = await session.execute(
        select(ProductNameLookup.product_id, ProductNameLookup.alias)
        .where(ProductNameLookup.alias.ilike(f"%{normalized_name}%"))
    )
    lookup_matches = res.all()
    
    # Если нашли совпадения в lookup, используем лучшее из них
    if lookup_matches:
        best_match = None
        best_score = 0
        
        for lookup_product_id, alias in lookup_matches:
            normalized_alias = clean_name_for_comparison(alias)
            score = fuzz.ratio(normalized_name, normalized_alias) / 100.0
            
            if score > best_score:
                best_score = score
                best_match = lookup_product_id
        
        if best_match and best_score >= threshold:
            return best_match, best_score
    
    # ──────────────────────── 2. RapidFuzz по каталогу ────────────────────
    rows = await session.execute(select(Product.id, Product.name))
    candidates = list(rows)  # [(id, name), …]
    
    if not candidates:  # пустой каталог
        return None, 0.0
    
    # Фильтруем полуфабрикаты, если требуется
    if exclude_semifinished:
        filtered_candidates = [(pid, name) for pid, name in candidates 
                               if not is_semifinished(name)]
        if filtered_candidates:  # Используем отфильтрованный список, только если он не пустой
            candidates = filtered_candidates
    
    # Подготавливаем нормализованные имена кандидатов для сравнения
    names_for_matching = [clean_name_for_comparison(name) for _, name in candidates]
    
    # Выполняем нечеткий поиск
    match = process.extractOne(normalized_name, names_for_matching, scorer=fuzz.ratio)
    
    if match:
        # Обработка результата extractOne
        if len(match) >= 3:
            matched_name, score_raw, idx = match  # score_raw 0–100, idx это индекс
        else:
            matched_name, score_raw = match  # score_raw 0–100
            idx = names_for_matching.index(matched_name)
        
        confidence = score_raw / 100.0
        if confidence >= threshold:
            # Находим product_id по индексу в исходном списке
            product_id = candidates[idx][0]
            
            # Сохраняем совпадение для будущего использования
            if confidence >= MIN_CONFIDENCE_FOR_LEARNING:
                await save_match_to_lookup(session, parsed_name, product_id, confidence)
            
            return product_id, confidence
    
    # ничего не подошло с нужным порогом
    return None, 0.0


async def get_product_suggestions(
    session: AsyncSession,
    parsed_name: str,
    limit: int = 5,
    exclude_semifinished: bool = True,
) -> List[Dict[str, Any]]:
    """
    Получает список предложений товаров для выбора пользователем.
    
    :param session: асинхронная сессия SQLAlchemy
    :param parsed_name: строка из OCR/Parsing
    :param limit: максимальное количество предложений
    :param exclude_semifinished: исключать ли полуфабрикаты
    :return: список словарей с данными о товарах и степени схожести
    """
    if not parsed_name:
        return []
    
    # Нормализуем имя для поиска
    normalized_name = clean_name_for_comparison(parsed_name)
    
    # Получаем список всех продуктов
    rows = await session.execute(select(Product.id, Product.name, Product.unit))
    candidates = list(rows)  # [(id, name, unit), …]
    
    if not candidates:
        return []
    
    # Фильтруем полуфабрикаты, если требуется
    if exclude_semifinished:
        candidates = [(pid, name, unit) for pid, name, unit in candidates 
                     if not is_semifinished(name)]
    
    # Подготавливаем нормализованные имена кандидатов для сравнения
    names_for_matching = [clean_name_for_comparison(name) for _, name, _ in candidates]
    
    # Получаем топ N лучших совпадений
    matches = process.extract(normalized_name, names_for_matching, 
                              scorer=fuzz.ratio, limit=limit)
    
    # Формируем результат
    suggestions = []
    for match in matches:
        if len(match) >= 3:
            matched_name, score_raw, idx = match
        else:
            matched_name, score_raw = match
            idx = names_for_matching.index(matched_name)
        
        product_id, name, unit = candidates[idx]
        confidence = score_raw / 100.0
        
        suggestions.append({
            'id': product_id,
            'name': name,
            'unit': unit,
            'confidence': confidence
        })
    
    return suggestions
