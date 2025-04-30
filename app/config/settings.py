"""Настройки приложения."""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Настройки приложения."""
    
    # Основные ключи
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("development", env="ENVIRONMENT")

    # GPT сервисы
    gpt_ocr_url: str = Field("https://api.openai.com/v1/chat/completions", env="GPT_OCR_URL")
    gpt_parsing_url: str = Field("https://api.openai.com/v1/chat/completions", env="GPT_PARSING_URL")

    # Syrve
    syrve_server_url: str = Field(..., env="SYRVE_SERVER_URL")
    syrve_login: str = Field(..., env="SYRVE_LOGIN")
    syrve_password: str = Field(..., env="SYRVE_PASSWORD")
    default_store_id: str = Field(..., env="DEFAULT_STORE_ID")

    # Пути к CSV
    products_csv: str = Field("data/base_products.csv", env="PRODUCTS_CSV")
    suppliers_csv: str = Field("data/base_suppliers.csv", env="SUPPLIERS_CSV")
    learned_products_csv: str = Field("data/learned_products.csv", env="LEARNED_PRODUCTS_CSV")
    learned_suppliers_csv: str = Field("data/learned_suppliers.csv", env="LEARNED_SUPPLIERS_CSV")

    # Fuzzy
    fuzzy_threshold: float = Field(0.85, env="FUZZY_THRESHOLD")

    # База данных
    database_url: str = Field(..., env="DATABASE_URL")

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