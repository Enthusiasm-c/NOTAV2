"""
app/config.py — централизованная конфигурация Nota V2
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ───────────────────  обязательные для продакшена  ──────────────────
    telegram_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(
        "sqlite+aiosqlite:///:memory:", alias="DATABASE_URL"
    )

    # ───────────────────────────  OpenAI  ───────────────────────────────
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    gpt_ocr_url: str = Field(
        "https://api.openai.com/v1/chat/completions", alias="GPT_OCR_URL"
    )
    gpt_parsing_url: str | None = Field(None, alias="GPT_PARSING_URL")

    # ───────────────────────────  Syrve  ────────────────────────────────
    syrve_url: str = Field("http://stub.local", alias="SYRVE_SERVER_URL")
    syrve_token: str | None = Field(None, alias="SYRVE_TOKEN")

    # ──────────────────────────  Matching  ──────────────────────────────
    fuzzy_threshold: float = Field(0.85, alias="FUZZY_THRESHOLD")

    # ───────────────────  pydantic-settings config  ────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
