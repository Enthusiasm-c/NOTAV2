# app/__init__.py
"""
Основной модуль приложения NOTA V2.

Этот модуль:
* Инициализирует логгер
* Загружает конфигурацию
* Загружает данные из CSV-файлов
"""

# --- Логирование --------------------------------------------------------
import structlog
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

# --- Конфигурация ------------------------------------------------------
from app.config.settings import get_settings
settings = get_settings()

# --- Данные -----------------------------------------------------------
from app.core.data_loader import load_data
load_data()  # Загружаем данные при старте приложения
