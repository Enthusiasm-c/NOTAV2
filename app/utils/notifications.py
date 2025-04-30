"""Утилиты для работы с уведомлениями."""

from typing import Any, Dict, List, Optional

from app.core.constants import NOTIFICATION_TYPES
from app.utils.logger import get_logger

logger = get_logger(__name__)

class NotificationManager:
    """Менеджер уведомлений."""

    def __init__(self):
        """Инициализирует менеджер уведомлений."""
        self._handlers = {}

    def register_handler(
        self,
        notification_type: str,
        handler: callable
    ) -> None:
        """Регистрирует обработчик уведомлений.

        Args:
            notification_type: Тип уведомления
            handler: Обработчик
        """
        if notification_type not in NOTIFICATION_TYPES:
            raise ValueError(f"Неизвестный тип уведомления: {notification_type}")

        self._handlers[notification_type] = handler
        logger.info(
            f"Зарегистрирован обработчик для типа уведомлений: {notification_type}"
        )

    def unregister_handler(self, notification_type: str) -> None:
        """Удаляет обработчик уведомлений.

        Args:
            notification_type: Тип уведомления
        """
        if notification_type in self._handlers:
            del self._handlers[notification_type]
            logger.info(
                f"Удален обработчик для типа уведомлений: {notification_type}"
            )

    async def send_notification(
        self,
        notification_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """Отправляет уведомление.

        Args:
            notification_type: Тип уведомления
            data: Данные уведомления

        Returns:
            bool: True если уведомление отправлено, иначе False
        """
        if notification_type not in NOTIFICATION_TYPES:
            logger.error(f"Неизвестный тип уведомления: {notification_type}")
            return False

        if notification_type not in self._handlers:
            logger.warning(
                f"Нет обработчика для типа уведомлений: {notification_type}"
            )
            return False

        try:
            handler = self._handlers[notification_type]
            await handler(data)
            logger.info(
                f"Уведомление отправлено: {notification_type}",
                extra={"data": data}
            )
            return True

        except Exception as e:
            logger.error(
                f"Ошибка при отправке уведомления: {notification_type}",
                extra={"error": str(e), "data": data}
            )
            return False

    def get_available_types(self) -> List[str]:
        """Получает список доступных типов уведомлений.

        Returns:
            List[str]: Список типов
        """
        return list(NOTIFICATION_TYPES.keys())

    def get_type_description(self, notification_type: str) -> Optional[str]:
        """Получает описание типа уведомления.

        Args:
            notification_type: Тип уведомления

        Returns:
            Optional[str]: Описание или None
        """
        return NOTIFICATION_TYPES.get(notification_type)

# Создаем глобальный экземпляр менеджера уведомлений
notification_manager = NotificationManager() 