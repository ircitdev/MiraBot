"""
Rate Limiter для бота поддержки.
Защита от спама - ограничение количества сообщений в минуту.
"""

from datetime import datetime, timedelta
from typing import Dict
from loguru import logger


class RateLimiter:
    """
    Rate limiter на основе in-memory словаря.
    Ограничивает количество сообщений в минуту от одного пользователя.
    """

    def __init__(self, limit: int = 10, window_seconds: int = 60):
        """
        Args:
            limit: Максимальное количество сообщений в окне
            window_seconds: Размер окна в секундах (по умолчанию 60 = 1 минута)
        """
        self.limit = limit
        self.window_seconds = window_seconds
        # Словарь: user_id -> список timestamp-ов сообщений
        self._messages: Dict[int, list[datetime]] = {}

    def check_limit(self, user_id: int) -> bool:
        """
        Проверяет, не превышен ли лимит для пользователя.

        Args:
            user_id: Telegram ID пользователя

        Returns:
            bool: True если можно отправить сообщение, False если лимит превышен
        """
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)

        # Получаем или создаём список сообщений пользователя
        if user_id not in self._messages:
            self._messages[user_id] = []

        # Удаляем старые сообщения (вне окна)
        self._messages[user_id] = [
            ts for ts in self._messages[user_id]
            if ts > window_start
        ]

        # Проверяем лимит
        current_count = len(self._messages[user_id])

        if current_count >= self.limit:
            logger.warning(
                f"Rate limit exceeded for user {user_id}: "
                f"{current_count}/{self.limit} messages in {self.window_seconds}s"
            )
            return False

        return True

    def increment(self, user_id: int) -> None:
        """
        Увеличивает счётчик сообщений для пользователя.

        Args:
            user_id: Telegram ID пользователя
        """
        now = datetime.now()

        if user_id not in self._messages:
            self._messages[user_id] = []

        self._messages[user_id].append(now)

        logger.debug(
            f"Rate limiter: user {user_id} sent message. "
            f"Count: {len(self._messages[user_id])}/{self.limit}"
        )

    def reset(self, user_id: int) -> None:
        """
        Сбрасывает счётчик для пользователя.

        Args:
            user_id: Telegram ID пользователя
        """
        if user_id in self._messages:
            del self._messages[user_id]
            logger.debug(f"Rate limiter reset for user {user_id}")

    def cleanup(self) -> None:
        """
        Очищает старые записи для всех пользователей.
        Рекомендуется вызывать периодически (например, раз в час).
        """
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)

        users_to_remove = []

        for user_id, timestamps in self._messages.items():
            # Удаляем старые timestamp-ы
            self._messages[user_id] = [
                ts for ts in timestamps
                if ts > window_start
            ]

            # Если список пустой, удаляем пользователя
            if not self._messages[user_id]:
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            del self._messages[user_id]

        if users_to_remove:
            logger.debug(f"Rate limiter cleaned up {len(users_to_remove)} users")


# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter(limit=10, window_seconds=60)
