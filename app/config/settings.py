"""Настройки приложения."""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from decouple import config


class Settings(BaseSettings):
    """Настройки приложения."""
    
    # База данных
    database_url: str = config("DATABASE_URL", default="postgresql+asyncpg://nota:StrongPass123@127.0.0.1/nota_db")
    
    # Telegram
    telegram_bot_token: str = config("TELEGRAM_BOT_TOKEN", default="")
    
    # OpenAI
    openai_api_key: str = config("OPENAI_API_KEY", default="")
    
    # Настройки логирования
    log_level: str = config("LOG_LEVEL", default="INFO")
    log_format: str = config("LOG_FORMAT", default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Настройки приложения
    debug: bool = config("DEBUG", default=False, cast=bool)
    environment: str = config("ENVIRONMENT", default="development")
    
    class Config:
        """Конфигурация Pydantic."""
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Получить настройки приложения."""
    return Settings()


settings = get_settings() 