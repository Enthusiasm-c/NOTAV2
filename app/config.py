# app/config.py
"""
Единая конфигурация Nota V2.

• Pydantic-settings (Pydantic v2).  
• Переменные берутся из `.env` или из окружения.  
• Безопасные дефолты позволяют запустить проект и CI без настоящих секретов.
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # /opt/notav2


class Settings(BaseSettings):
    # ───────────────────────── Обязательные в проде ──────────────────────────
    telegram_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")

    database_url: str = Field(
        "sqlite+aiosqlite:///:memory:", alias="DATABASE_URL"
    )

    # ──────────────────────── OpenAI / GPT-OCR / Parsing ─────────────────────
    openai_api_key: str | None = Field(
        None, alias="OPENAI_API_KEY"
    )

    gpt_ocr_url: str = Field(
        "https://api.openai.com/v1/chat/completions", alias="GPT_OCR_URL"
    )

    gpt_parsing_url: str | None = Field(
        None, alias="GPT_PARSING_URL"
    )

    # ────────────────────────────── Syrve API ────────────────────────────────
    syrve_server_url: str = Field(
        "http://stub.local", alias="SYRVE_SERVER_URL"
    )
    syrve_token: str | None = Field(None, alias="SYRVE_TOKEN")
    syrve_login: str | None = Field(None, alias="SYRVE_LOGIN")
    syrve_password: str | None = Field(None, alias="SYRVE_PASSWORD")
    default_store_id: str | None = Field(None, alias="DEFAULT_STORE_ID")

    # ─────────────────────────── Fuzzy-поиск ─────────────────────────────────
    fuzzy_threshold: float = Field(0.85, alias="FUZZY_THRESHOLD")

    # ─────────────────────── pydantic-settings config ───────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─────────────────────────── helper-свойства ────────────────────────────
    @property
    def syrve_url(self) -> str:  # для обратной совместимости
        return self.syrve_server_url


settings = Settings()
