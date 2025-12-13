"""
Retry логика для API вызовов.
Повторные попытки при ошибках API Claude/Whisper.
"""

import asyncio
from functools import wraps
from typing import Callable, Any, Type, Tuple
from loguru import logger


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Декоратор для повторных попыток при ошибках.

    Args:
        max_attempts: Максимальное количество попыток.
        delay: Начальная задержка между попытками (секунды).
        backoff: Множитель задержки (экспоненциальный backoff).
        exceptions: Типы исключений, при которых нужно повторять.

    Example:
        @async_retry(max_attempts=3, delay=1.0, exceptions=(APIError,))
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func.__name__}: attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__}: all {max_attempts} attempts failed. "
                            f"Last error: {e}"
                        )

            raise last_exception

        return wrapper
    return decorator


class RetryableError(Exception):
    """Базовый класс для ошибок, которые можно повторить."""
    pass


class APIError(RetryableError):
    """Ошибка API (Claude, Whisper и т.д.)."""
    pass


class RateLimitError(RetryableError):
    """Превышен лимит запросов."""
    pass


class TimeoutError(RetryableError):
    """Таймаут запроса."""
    pass
