"""Утилиты для работы с поиском."""

from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
import re

from rapidfuzz import fuzz, process

from app.core.constants import FUZZY_MATCH_THRESHOLD, MAX_SEARCH_RESULTS

def normalize_text(text: str) -> str:
    """
    Нормализует текст для поиска:
    - Приводит к нижнему регистру
    - Удаляет специальные символы
    - Удаляет лишние пробелы
    """
    if not text:
        return ""
    # Приводим к нижнему регистру
    text = text.lower()
    # Удаляем специальные символы, оставляем только буквы, цифры и пробелы
    text = re.sub(r'[^a-zа-яё0-9\s]', '', text)
    # Заменяем множественные пробелы на один
    text = re.sub(r'\s+', ' ', text)
    # Удаляем пробелы в начале и конце
    return text.strip()

def fuzzy_search(query: str, items: List[Dict[str, Any]], 
                threshold: float = 0.6) -> List[Tuple[Dict[str, Any], float]]:
    """
    Выполняет нечеткий поиск по списку элементов.
    
    Args:
        query: Строка поиска
        items: Список словарей для поиска
        threshold: Порог схожести (0.0 - 1.0)
        
    Returns:
        Список кортежей (элемент, оценка схожести)
    """
    if not query or not items:
        return []
        
    normalized_query = normalize_text(query)
    results = []
    
    for item in items:
        # Ищем по всем строковым полям
        max_score = 0.0
        for value in item.values():
            if isinstance(value, str):
                score = SequenceMatcher(None, 
                                      normalized_query, 
                                      normalize_text(value)).ratio()
                max_score = max(max_score, score)
                
        if max_score >= threshold:
            results.append((item, max_score))
            
    # Сортируем по убыванию схожести
    return sorted(results, key=lambda x: x[1], reverse=True)

def fuzzy_search_one(query: str, items: List[Dict[str, Any]], 
                    threshold: float = 0.6) -> Optional[Tuple[Dict[str, Any], float]]:
    """
    Выполняет нечеткий поиск и возвращает лучший результат.
    
    Args:
        query: Строка поиска
        items: Список словарей для поиска
        threshold: Порог схожести (0.0 - 1.0)
        
    Returns:
        Кортеж (лучший элемент, оценка схожести) или None
    """
    results = fuzzy_search(query, items, threshold)
    return results[0] if results else None

def token_sort_ratio(
    query: str,
    choice: str
) -> int:
    """Вычисляет коэффициент схожести с учетом порядка токенов.

    Args:
        query: Поисковый запрос
        choice: Вариант для сравнения

    Returns:
        int: Коэффициент схожести
    """
    return fuzz.token_sort_ratio(query, choice)

def token_set_ratio(
    query: str,
    choice: str
) -> int:
    """Вычисляет коэффициент схожести без учета порядка токенов.

    Args:
        query: Поисковый запрос
        choice: Вариант для сравнения

    Returns:
        int: Коэффициент схожести
    """
    return fuzz.token_set_ratio(query, choice)

def partial_ratio(
    query: str,
    choice: str
) -> int:
    """Вычисляет коэффициент частичного совпадения.

    Args:
        query: Поисковый запрос
        choice: Вариант для сравнения

    Returns:
        int: Коэффициент схожести
    """
    return fuzz.partial_ratio(query, choice)

def ratio(
    query: str,
    choice: str
) -> int:
    """Вычисляет коэффициент схожести.

    Args:
        query: Поисковый запрос
        choice: Вариант для сравнения

    Returns:
        int: Коэффициент схожести
    """
    return fuzz.ratio(query, choice) 