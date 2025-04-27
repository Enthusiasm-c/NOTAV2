# app/config.py
"""
Global configuration for Nota V2.

• Uses *pydantic-settings* (Pydantic v2).  
• Reads variables from **.env** or process-environment.  
• Safe defaults allow tests/CI to run without a real .env.

Rename or override any value in production by
exporting an environment variable or editing .env.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # /opt/notav2


class Settings(BaseSettings):
    # ─────────────────────────── Telegram ────────────────────────────────
    telegram_token: str = Field(
        "DUMMY_TG_TOKEN",                # << safe default for CI
        alias="TELEGRAM_BOT_TOKEN",
    )

    # ─────────────────────────── Database ────────────────────────────────
    database_url: str = Field(
        "sqlite+aiosqlite:///:memory:",   # in-memory for tests
        alias="DATABASE_URL",
    )

    # ─────────────────────────── OpenAI / GPT ────────────────────────────
    openai_api_key: str | None = Field(
        None, alias="OPENAI_API_KEY"
    )
    gpt_ocr_url: str = Field(
        "https://api.openai.com/v1/chat/completions",
        alias="GPT_OCR_URL",
    )
    gpt_parsing_url: str | None = Field(
        None, alias="GPT_PARSING_URL"
    )

    # ───────────────────────────── Syrve API ─────────────────────────────
    syrve_server_url: str = Field(
        "http://stub.local", alias="SYRVE_SERVER_URL"
    )
    syrve_token: str | None = Field(None, alias="SYRVE_TOKEN")
    syrve_login: str | None = Field(None, alias="SYRVE_LOGIN")
    syrve_password: str | None = Field(None, alias="SYRVE_PASSWORD")
    default_store_id: str | None = Field(None, alias="DEFAULT_STORE_ID")

    # ────────────────────────── Matching params ──────────────────────────
    fuzzy_threshold: float = Field(
        0.85, alias="FUZZY_THRESHOLD"
    )

    # ──────────────────────── pydantic-settings cfg ──────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─────────────────────────── helper aliases ──────────────────────────
    @property
    def syrve_url(self) -> str:  # legacy name used elsewhere
        return self.syrve_server_url


settings = Settings()
