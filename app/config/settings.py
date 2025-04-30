from dotenv import load_dotenv
load_dotenv()

"""Настройки приложения."""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", alias="LOG_FORMAT")
    debug: bool = Field(False, alias="DEBUG")
    environment: str = Field("development", alias="ENVIRONMENT")
    gpt_ocr_url: str = Field("https://api.openai.com/v1/chat/completions", alias="GPT_OCR_URL")
    gpt_parsing_url: str = Field("https://api.openai.com/v1/chat/completions", alias="GPT_PARSING_URL")
    syrve_server_url: str = Field(..., alias="SYRVE_SERVER_URL")
    syrve_login: str = Field(..., alias="SYRVE_LOGIN")
    syrve_password: str = Field(..., alias="SYRVE_PASSWORD")
    default_store_id: str = Field(..., alias="DEFAULT_STORE_ID")
    products_csv: str = Field("data/base_products.csv", alias="PRODUCTS_CSV")
    suppliers_csv: str = Field("data/base_suppliers.csv", alias="SUPPLIERS_CSV")
    learned_products_csv: str = Field("data/learned_products.csv", alias="LEARNED_PRODUCTS_CSV")
    learned_suppliers_csv: str = Field("data/learned_suppliers.csv", alias="LEARNED_SUPPLIERS_CSV")
    fuzzy_threshold: float = Field(0.85, alias="FUZZY_THRESHOLD")
    database_url: str = Field(..., alias="DATABASE_URL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# settings = get_settings() 