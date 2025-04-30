"""Настройки приложения."""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Настройки приложения."""
    
    # Настройки базы данных
    DATABASE_URL: str = "sqlite+aiosqlite:///./nota.db"
    
    # Настройки Telegram бота
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    
    # Настройки OpenAI
    OPENAI_API_KEY: Optional[str] = None
    
    # Настройки Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    
    class Config:
        """Конфигурация настроек."""
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings() 