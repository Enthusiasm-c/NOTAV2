"""
app/config.py
~~~~~~~~~~~~~

Единая точка загрузки конфигурации приложения.

* Используем Pydantic-v2 + pydantic-settings.
* Все параметры читаются из `.env` **или** из переменных окружения.
* Для локального запуска / CI заданы безопасные значения-по-умолчанию,
  поэтому импорт `settings` не падает, даже если переменные не прописаны.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- обязательные данные для продакшена -------------------------------
    telegram_token: str = "DUMMY_TG_TOKEN"
    db_url: str = "sqlite+aiosqlite:///:memory:"         # in-memory БД для тестов
    syrve_url: str = "http://stub.local"                 # заглушка API

    # --- прочие параметры -------------------------------------------------
    gpt_ocr_url: str = "https://gpt-ocr/"                # Vision-OCR endpoint
    gpt_parsing_url: str = "https://gpt-parse/"          # Struct-parser endpoint
    fuzzy_threshold: float = 0.85                        # RapidFuzz порог
    syrve_token: str | None = None                       # опциональный Bearer

    # --- pydantic-settings config ----------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",             # читаем переменные из файла
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
