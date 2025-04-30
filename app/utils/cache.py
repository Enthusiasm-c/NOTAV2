"""Утилиты для работы с кэшем."""

import json
from typing import Any, Optional

from app.core.constants import CACHE_PREFIX, CACHE_TTL

# Простой in-memory кэш
_cache = {}

def get_cache_key(key: str) -> str:
    """Получает ключ кэша.

    Args:
        key: Ключ

    Returns:
        str: Полный ключ кэша
    """
    return f"{CACHE_PREFIX}{key}"

def get(key: str) -> Optional[Any]:
    """Получает значение из кэша.

    Args:
        key: Ключ

    Returns:
        Optional[Any]: Значение или None
    """
    cache_key = get_cache_key(key)
    if cache_key in _cache:
        return _cache[cache_key]
    return None

def set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """Устанавливает значение в кэш.

    Args:
        key: Ключ
        value: Значение
        ttl: Время жизни в секундах
    """
    cache_key = get_cache_key(key)
    _cache[cache_key] = value

def delete(key: str) -> None:
    """Удаляет значение из кэша.

    Args:
        key: Ключ
    """
    cache_key = get_cache_key(key)
    if cache_key in _cache:
        del _cache[cache_key]

def clear() -> None:
    """Очищает кэш."""
    _cache.clear()

def get_or_set(
    key: str,
    default_func: callable,
    ttl: Optional[int] = None
) -> Any:
    """Получает значение из кэша или устанавливает новое.

    Args:
        key: Ключ
        default_func: Функция для получения значения по умолчанию
        ttl: Время жизни в секундах

    Returns:
        Any: Значение
    """
    value = get(key)
    if value is None:
        value = default_func()
        set(key, value, ttl)
    return value

def cache_json(key: str, value: Any) -> None:
    """Кэширует значение в формате JSON.

    Args:
        key: Ключ
        value: Значение
    """
    cache_key = get_cache_key(key)
    _cache[cache_key] = json.dumps(value)

def get_json(key: str) -> Optional[Any]:
    """Получает значение из кэша в формате JSON.

    Args:
        key: Ключ

    Returns:
        Optional[Any]: Значение или None
    """
    cache_key = get_cache_key(key)
    if cache_key in _cache:
        return json.loads(_cache[cache_key])
    return None 