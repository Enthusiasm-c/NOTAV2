from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_token: str
    db_url: str
    gpt_ocr_url: str = "https://gpt-ocr/"
    gpt_parsing_url: str = "https://gpt-parse/"
    fuzzy_threshold: float = 0.85
    syrve_url: str
    syrve_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()
