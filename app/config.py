# app/config.py
"""
Nota V2 — центральная конфигурация проекта
-----------------------------------------

* Используем **pydantic-settings** (Pydantic v2).
* Значения берутся из файла `.env` или переменных окружения.
* Безопасные дефолты позволяют запускать приложение и CI-pipeline
  даже без настоящих секретов.

Изменения 2025-04-28
────────────────────
1. Добавлено поле ``log_level`` (DEBUG / INFO / …).
2. В ``model_config`` выставлено ``extra="ignore"`` — лишние ключи .env
   больше не валят сервис (удобно на MVP).
3. Логика и алиасы прежних полей сохранены.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # /opt/notav2


class Settings(BaseSettings):
    # ───────────────────────── Telegram ────────────────────────────────
    telegram_token: str = Field(
        "DUMMY_TG_TOKEN", alias="TELEGRAM_BOT_TOKEN"
    )

    # ───────────────────────── Database ────────────────────────────────
    database_url: str = Field(
        "sqlite+aiosqlite:///:memory:", alias="DATABASE_URL"
    )

    # ───────────────────────── OpenAI / GPT ────────────────────────────
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    gpt_ocr_url: str = Field(
        "https://api.openai.com/v1/chat/completions", alias="GPT_OCR_URL"
    )
    gpt_parsing_url: str | None = Field(None, alias="GPT_PARSING_URL")

    # ───────────────────────────── Syrve API ───────────────────────────
    syrve_server_url: str = Field(
        "http://stub.local", alias="SYRVE_SERVER_URL"
    )
    syrve_token: str | None = Field(None, alias="SYRVE_TOKEN")
    syrve_login: str | None = Field(None, alias="SYRVE_LOGIN")
    syrve_password: str | None = Field(None, alias="SYRVE_PASSWORD")
    default_store_id: str | None = Field(None, alias="DEFAULT_STORE_ID")

    # ────────────────────────── CSV-файлы ──────────────────────────────
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

    # ────────────────────────── Алгоритмы ──────────────────────────────
    fuzzy_threshold: float = Field(0.85, alias="FUZZY_THRESHOLD")

    # ────────────────────────── Логирование ────────────────────────────
    log_level: str = Field("INFO", alias="LOG_LEVEL")  # NEW

    # ─────────────────── pydantic-settings config ──────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",              # NEW — неизвестные ключи безопасно игнорируем
    )

    # ───────────────────── helper-alias (legacy) ───────────────────────
    @property
    def syrve_url(self) -> str:        # поддержка старого имени
        return self.syrve_server_url

    @property
    def db_url(self) -> str:           # поддержка прежних импортов
        return self.database_url


settings = Settings()
