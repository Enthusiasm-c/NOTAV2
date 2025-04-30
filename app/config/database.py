"""
Конфигурация базы данных.

Этот модуль содержит настройки и инициализацию базы данных.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config.settings import get_settings
from app.models.base import Base

def get_engine_and_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False, future=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, SessionLocal 