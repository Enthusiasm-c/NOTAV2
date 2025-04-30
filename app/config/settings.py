"""Настройки приложения."""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("development", env="ENVIRONMENT")
    gpt_ocr_url: str = Field("https://api.openai.com/v1/chat/completions", env="GPT_OCR_URL")
    gpt_parsing_url: str = Field("https://api.openai.com/v1/chat/completions", env="GPT_PARSING_URL")
    syrve_server_url: str = Field(..., env="SYRVE_SERVER_URL")
    syrve_login: str = Field(..., env="SYRVE_LOGIN")
    syrve_password: str = Field(..., env="SYRVE_PASSWORD")
    default_store_id: str = Field(..., env="DEFAULT_STORE_ID")
    products_csv: str = Field("data/base_products.csv", env="PRODUCTS_CSV")
    suppliers_csv: str = Field("data/base_suppliers.csv", env="SUPPLIERS_CSV")
    learned_products_csv: str = Field("data/learned_products.csv", env="LEARNED_PRODUCTS_CSV")
    learned_suppliers_csv: str = Field("data/learned_suppliers.csv", env="LEARNED_SUPPLIERS_CSV")
    fuzzy_threshold: float = Field(0.85, env="FUZZY_THRESHOLD")
    database_url: str = Field(..., env="DATABASE_URL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 