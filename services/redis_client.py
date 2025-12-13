"""
Redis client service.
Асинхронный клиент для работы с Redis.
"""

import redis.asyncio as redis
from typing import Optional, Any
from loguru import logger

from config.settings import settings


class RedisClient:
    """Асинхронный клиент Redis."""

    _instance: Optional["RedisClient"] = None
    _redis: Optional[redis.Redis] = None

    def __new__(cls) -> "RedisClient":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Подключается к Redis."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
                # Проверяем подключение
                await self._redis.ping()
                logger.info(f"Connected to Redis: {settings.REDIS_URL}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory fallback.")
                self._redis = None

    async def disconnect(self) -> None:
        """Отключается от Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Disconnected from Redis")

    @property
    def is_connected(self) -> bool:
        """Проверяет, подключен ли Redis."""
        return self._redis is not None

    async def get(self, key: str) -> Optional[str]:
        """Получает значение по ключу."""
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
    ) -> bool:
        """
        Устанавливает значение.

        Args:
            key: Ключ
            value: Значение
            expire: Время жизни в секундах
        """
        if not self._redis:
            return False
        try:
            await self._redis.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Удаляет ключ."""
        if not self._redis:
            return False
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Проверяет существование ключа."""
        if not self._redis:
            return False
        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Возвращает TTL ключа в секундах."""
        if not self._redis:
            return -2
        try:
            return await self._redis.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL error: {e}")
            return -2

    async def incr(self, key: str) -> int:
        """Инкрементирует значение."""
        if not self._redis:
            return 0
        try:
            return await self._redis.incr(key)
        except Exception as e:
            logger.error(f"Redis INCR error: {e}")
            return 0

    async def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Устанавливает значение с TTL."""
        if not self._redis:
            return False
        try:
            await self._redis.setex(key, seconds, value)
            return True
        except Exception as e:
            logger.error(f"Redis SETEX error: {e}")
            return False


# Глобальный экземпляр
redis_client = RedisClient()
