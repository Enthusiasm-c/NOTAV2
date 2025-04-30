"""Настройки приложения."""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Настройки приложения."""
    
    # База данных
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Telegram
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    
    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # Настройки логирования
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")
    
    # Настройки приложения
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("development", env="ENVIRONMENT")
    
    class Config:
        """Конфигурация Pydantic."""
        env_file = ".env"
        case_sensitive = True
        extra = "forbid"


@lru_cache()
def get_settings() -> Settings:
    """Получить настройки приложения."""
    return Settings()


settings = get_settings() 