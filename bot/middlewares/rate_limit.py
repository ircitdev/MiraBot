"""
Rate limiting middleware.
Защита от спама — максимум 1 сообщение в 2 секунды.
Поддерживает Redis для персистентности между перезапусками.
"""

import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from services.redis_client import redis_client


class RateLimiter:
    """
    Rate limiter для защиты от спама.
    Использует Redis если доступен, иначе fallback на in-memory.
    """

    REDIS_KEY_PREFIX = "rate_limit:"

    def __init__(self, min_interval: float = 2.0):
        """
        Args:
            min_interval: Минимальный интервал между сообщениями в секундах.
        """
        self.min_interval = min_interval
        # Fallback для случаев когда Redis недоступен
        self._last_message_time: dict[int, float] = defaultdict(float)

    async def is_allowed(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь отправить сообщение."""
        now = time.time()

        # Пробуем Redis
        if redis_client.is_connected:
            return await self._check_redis(user_id, now)

        # Fallback на in-memory
        return self._check_memory(user_id, now)

    def _check_memory(self, user_id: int, now: float) -> bool:
        """In-memory проверка (fallback)."""
        last_time = self._last_message_time[user_id]

        if now - last_time < self.min_interval:
            return False

        self._last_message_time[user_id] = now
        return True

    async def _check_redis(self, user_id: int, now: float) -> bool:
        """Redis-based проверка."""
        key = f"{self.REDIS_KEY_PREFIX}{user_id}"

        try:
            last_time_str = await redis_client.get(key)

            if last_time_str:
                last_time = float(last_time_str)
                if now - last_time < self.min_interval:
                    return False

            # Записываем новое время с TTL = min_interval + 1 сек
            await redis_client.setex(
                key,
                int(self.min_interval) + 1,
                str(now),
            )
            return True

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fallback на in-memory при ошибке
            return self._check_memory(user_id, now)

    async def get_wait_time(self, user_id: int) -> float:
        """Возвращает время ожидания до следующего сообщения."""
        now = time.time()

        # Пробуем Redis
        if redis_client.is_connected:
            key = f"{self.REDIS_KEY_PREFIX}{user_id}"
            try:
                last_time_str = await redis_client.get(key)
                if last_time_str:
                    last_time = float(last_time_str)
                    wait = self.min_interval - (now - last_time)
                    return max(0, wait)
            except Exception:
                pass

        # Fallback на in-memory
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

    if not await rate_limiter.is_allowed(user_id):
        wait_time = await rate_limiter.get_wait_time(user_id)
        logger.warning(f"Rate limit exceeded for user {user_id}, wait {wait_time:.1f}s")

        # Не отвечаем слишком часто, чтобы не создавать спам
        # Просто игнорируем сообщение
        return False

    return True
