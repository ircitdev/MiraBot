"""
Rate limiting middleware.
Защита от спама — максимум 1 сообщение в 2 секунды.
"""

import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger


class RateLimiter:
    """Rate limiter для защиты от спама."""

    def __init__(self, min_interval: float = 2.0):
        """
        Args:
            min_interval: Минимальный интервал между сообщениями в секундах.
        """
        self.min_interval = min_interval
        self._last_message_time: dict[int, float] = defaultdict(float)

    def is_allowed(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь отправить сообщение."""
        now = time.time()
        last_time = self._last_message_time[user_id]

        if now - last_time < self.min_interval:
            return False

        self._last_message_time[user_id] = now
        return True

    def get_wait_time(self, user_id: int) -> float:
        """Возвращает время ожидания до следующего сообщения."""
        now = time.time()
        last_time = self._last_message_time[user_id]
        wait = self.min_interval - (now - last_time)
        return max(0, wait)


# Глобальный rate limiter
rate_limiter = RateLimiter(min_interval=2.0)


async def check_rate_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет rate limit для пользователя.

    Returns:
        True если сообщение можно обработать, False если rate limit превышен.
    """
    if not update.effective_user:
        return True

    user_id = update.effective_user.id

    if not rate_limiter.is_allowed(user_id):
        wait_time = rate_limiter.get_wait_time(user_id)
        logger.warning(f"Rate limit exceeded for user {user_id}, wait {wait_time:.1f}s")

        # Не отвечаем слишком часто, чтобы не создавать спам
        # Просто игнорируем сообщение
        return False

    return True
