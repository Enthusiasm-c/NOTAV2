"""
Конфигурация хранилища данных.
"""
import pathlib
from functools import lru_cache

from app.config.settings import get_settings

@lru_cache()
def get_data_dir() -> pathlib.Path:
    """
    Возвращает путь к директории с данными.
    Использует значение из настроек или дефолтное значение.
    """
    settings = get_settings()
    data_dir = pathlib.Path(settings.data_dir if hasattr(settings, 'data_dir') else 'data')
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir 