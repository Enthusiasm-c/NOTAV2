from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings

import app.models          # ← это подтягивает product / invoice / invoice_item
from app.models.base import Base


Base = declarative_base()
engine = create_async_engine(settings.db_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
