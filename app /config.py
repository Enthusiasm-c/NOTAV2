__all__ = ["settings"]

from pydantic import BaseSettings

class Settings(BaseSettings):
    """App config

    Variables:
        telegram_token: str    # Токен Telegram-бота
        db_url: str      # URI для подключения к PostgreSQL
        gpt_ocr_url: str
        gpt_parsing_url: str
        fuzzy_threshold: float
        syrve_url: str
        syrve_token: str|None
    """

    telegram_token: str = "TELEGRAM_TOKEN"
    db_url: str = "postgresql+asyncpg://user:pass@localhost/invoices_db"
    gpt_ocr_url: str = "http://localhost:8001/gpt-ocr"        # Dummy/mock
    gpt_parsing_url: str = "http://localhost:8001/gpt-parse"
    fuzzy_threshold: float = 0.9
    syrve_url: str = "http://localhost:8080/syrve"
    syrve_token: str | None = None  # TODO: Заполнить реальный ключ

settings = Settings()
