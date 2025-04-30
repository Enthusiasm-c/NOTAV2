"""Утилиты для работы с файлами."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.constants import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    UPLOAD_DIR,
)

def get_file_extension(filename: str) -> str:
    """Получает расширение файла.

    Args:
        filename: Имя файла

    Returns:
        str: Расширение файла
    """
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename: str) -> bool:
    """Проверяет, разрешен ли файл.

    Args:
        filename: Имя файла

    Returns:
        bool: True если файл разрешен, иначе False
    """
    return get_file_extension(filename) in ALLOWED_EXTENSIONS

def is_valid_file_size(file_size: int) -> bool:
    """Проверяет размер файла.

    Args:
        file_size: Размер файла в байтах

    Returns:
        bool: True если размер допустим, иначе False
    """
    return file_size <= MAX_UPLOAD_SIZE

def create_upload_dir() -> Path:
    """Создает директорию для загрузки файлов.

    Returns:
        Path: Путь к директории
    """
    upload_dir = Path(UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir

def get_unique_filename(filename: str) -> str:
    """Генерирует уникальное имя файла.

    Args:
        filename: Имя файла

    Returns:
        str: Уникальное имя файла
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    return f"{name}_{timestamp}{ext}"

def save_file(
    file_path: str,
    destination: Optional[str] = None
) -> Tuple[bool, str]:
    """Сохраняет файл.

    Args:
        file_path: Путь к файлу
        destination: Путь назначения

    Returns:
        Tuple[bool, str]: (Успех, Сообщение)
    """
    try:
        if not os.path.exists(file_path):
            return False, "Файл не найден"

        if not is_allowed_file(file_path):
            return False, "Недопустимый тип файла"

        file_size = os.path.getsize(file_path)
        if not is_valid_file_size(file_size):
            return False, "Размер файла превышает допустимый"

        upload_dir = create_upload_dir()
        filename = os.path.basename(file_path)
        unique_filename = get_unique_filename(filename)
        destination = destination or str(upload_dir / unique_filename)

        shutil.copy2(file_path, destination)
        return True, destination

    except Exception as e:
        return False, str(e)

def delete_file(file_path: str) -> Tuple[bool, str]:
    """Удаляет файл.

    Args:
        file_path: Путь к файлу

    Returns:
        Tuple[bool, str]: (Успех, Сообщение)
    """
    try:
        if not os.path.exists(file_path):
            return False, "Файл не найден"

        os.remove(file_path)
        return True, "Файл успешно удален"

    except Exception as e:
        return False, str(e)

def list_files(
    directory: Optional[str] = None,
    pattern: Optional[str] = None
) -> List[str]:
    """Получает список файлов.

    Args:
        directory: Директория
        pattern: Шаблон поиска

    Returns:
        List[str]: Список файлов
    """
    directory = directory or UPLOAD_DIR
    if not os.path.exists(directory):
        return []

    files = []
    for filename in os.listdir(directory):
        if pattern and not filename.endswith(pattern):
            continue
        if os.path.isfile(os.path.join(directory, filename)):
            files.append(filename)

    return files 