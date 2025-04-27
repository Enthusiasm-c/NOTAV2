# app/config.py
"""
Единая конфигурация Nota V2.

▪ Читаем переменные из файла .env **или** из окружения.
▪ Поддерживаем Pydantic v2 + pydantic-settings.
▪ Даём безопасные значения по умолчанию — поэтому локальный запуск и CI
  проходят даже без .env.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # /opt/notav2


class Settings(BaseSettings):
    # ──────────────────────────── ОБЯЗАТЕЛЬНЫЕ ДЛЯ ПРОДА ─────────────────────────
    telegram_token: str = Field(
        "DUMMY_TG_TOKEN", alias="TELEGRAM_BOT_TOKEN"
    )
    db_url: str = Field(
        "sqlite+aiosqlite:///:memory:", alias="DATABASE_URL"
    )

    # ───────────────────────────── GPT / OpenAI  ──────────────────────────────
    openai_api_key: str | None = Field(
        None, alias="OPENAI_API_KEY"
    )
    gpt_ocr_url: str = Field(
        "https://gpt-ocr/", alias="GPT_OCR_URL"
    )
    gpt_parsing_url: str = Field(
        "https://gpt-parse/", alias="GPT_PARSING_URL"
    )

    # ────────────────────────────── Syrve  ───────────────────────────────────
    syrve_server_url: str = Field(
        "http://stub.local", alias="SYRVE_SERVER_URL"
    )
    syrve_login: str | None = Field(
        None, alias="SYRVE_LOGIN"
    )
    syrve_password: str | None = Field(
        None, alias="SYRVE_PASSWORD"
    )
    syrve_token: str | None = Field(
        None, alias="SYRVE_TOKEN"
    )
    default_store_id: str | None = Field(
        None, alias="DEFAULT_STORE_ID"
    )

    # ─────────────────────────────── Matching  ───────────────────────────────
    fuzzy_threshold: float = Field(
        0.85, alias="FUZZY_THRESHOLD"
    )

    # ────────────────────────────── CSV-файлы  ───────────────────────────────
    products_csv: str = Field(
        "data/base_products.csv", alias="PRODUCTS_CSV"
    )
    suppliers_csv: str = Field(
        "data/base_suppliers.csv", alias="SUPPLIERS_CSV"
    )
    learned_products_csv: str = Field(
        "data/learned_products.csv", alias="LEARNED_PRODUCTS_CSV"
    )
    learned_suppliers_csv: str = Field(
        "data/learned_suppliers.csv", alias="LEARNED_SUPPLIERS_CSV"
    )

    # ────────────────────────────── Pydantic cfg ──────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─────────────────────────────── helpers ──────────────────────────────────
    @property
    def syrve_url(self) -> str:  # оставляем старое имя для обратной совместимости
        return self.syrve_server_url


settings = Settings()
