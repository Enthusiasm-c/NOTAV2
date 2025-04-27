# app/config.py
"""
Global configuration for Nota V2 (aiogram 3, Python 3.11).

• Основано на *pydantic-settings* (Pydantic v2).
• Переменные читаются из «.env» или из окружения.
• Безопасные значения-по-умолчанию позволяют запускать проект и CI даже,
  когда настоящие секреты не заданы.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  #  /opt/notav2


class Settings(BaseSettings):
    # ───────────────────────── Telegram ────────────────────────────────
    telegram_token: str = Field(
        "DUMMY_TG_TOKEN",                # safe default for tests / CI
        alias="TELEGRAM_BOT_TOKEN",
    )

    # ───────────────────────── Database ────────────────────────────────
    database_url: str = Field(
        "sqlite+aiosqlite:///:memory:",   # in-memory for CI
        alias="DATABASE_URL",
    )

    # ───────────────────────── OpenAI / GPT ────────────────────────────
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    gpt_ocr_url: str = Field(
        "https://api.openai.com/v1/chat/completions", alias="GPT_OCR_URL"
    )
    gpt_parsing_url: str | None = Field(None, alias="GPT_PARSING_URL")

    # ───────────────────────────── Syrve API ───────────────────────────
    syrve_server_url: str = Field("http://stub.local", alias="SYRVE_SERVER_URL")
    syrve_token: str | None = Field(None, alias="SYRVE_TOKEN")
    syrve_login: str | None = Field(None, alias="SYRVE_LOGIN")
    syrve_password: str | None = Field(None, alias="SYRVE_PASSWORD")
    default_store_id: str | None = Field(None, alias="DEFAULT_STORE_ID")

    # ──────────────────────── Matching params ──────────────────────────
    fuzzy_threshold: float = Field(0.85, alias="FUZZY_THRESHOLD")

    # ───────────────────── pydantic-settings cfg ───────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ───────────────────────── helper aliases ──────────────────────────
    @property
    def syrve_url(self) -> str:  # legacy name, used elsewhere
        return self.syrve_server_url

    @property
    def db_url(self) -> str:     # legacy alias for earlier imports/tests
        return self.database_url


settings = Settings()
