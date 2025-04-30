"""Утилиты для работы с базой данных."""

from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

async def get_by_id(
    session: AsyncSession,
    model: Type[ModelType],
    id: int
) -> Optional[ModelType]:
    """Получает объект по ID.

    Args:
        session: Сессия базы данных
        model: Модель
        id: ID объекта

    Returns:
        Optional[ModelType]: Объект или None
    """
    result = await session.execute(select(model).where(model.id == id))
    return result.scalar_one_or_none()

async def get_all(
    session: AsyncSession,
    model: Type[ModelType],
    skip: int = 0,
    limit: int = 100
) -> List[ModelType]:
    """Получает все объекты.

    Args:
        session: Сессия базы данных
        model: Модель
        skip: Количество пропускаемых объектов
        limit: Максимальное количество объектов

    Returns:
        List[ModelType]: Список объектов
    """
    result = await session.execute(
        select(model).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create(
    session: AsyncSession,
    model: Type[ModelType],
    data: Dict[str, Any]
) -> ModelType:
    """Создает новый объект.

    Args:
        session: Сессия базы данных
        model: Модель
        data: Данные для создания

    Returns:
        ModelType: Созданный объект
    """
    obj = model(**data)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj

async def update(
    session: AsyncSession,
    model: Type[ModelType],
    id: int,
    data: Dict[str, Any]
) -> Optional[ModelType]:
    """Обновляет объект.

    Args:
        session: Сессия базы данных
        model: Модель
        id: ID объекта
        data: Данные для обновления

    Returns:
        Optional[ModelType]: Обновленный объект или None
    """
    obj = await get_by_id(session, model, id)
    if obj:
        for key, value in data.items():
            setattr(obj, key, value)
        await session.commit()
        await session.refresh(obj)
    return obj

async def delete(
    session: AsyncSession,
    model: Type[ModelType],
    id: int
) -> bool:
    """Удаляет объект.

    Args:
        session: Сессия базы данных
        model: Модель
        id: ID объекта

    Returns:
        bool: True если объект удален, иначе False
    """
    obj = await get_by_id(session, model, id)
    if obj:
        await session.delete(obj)
        await session.commit()
        return True
    return False

async def execute_query(
    session: AsyncSession,
    query: Select
) -> List[Any]:
    """Выполняет произвольный запрос.

    Args:
        session: Сессия базы данных
        query: Запрос

    Returns:
        List[Any]: Результаты запроса
    """
    result = await session.execute(query)
    return result.scalars().all() 