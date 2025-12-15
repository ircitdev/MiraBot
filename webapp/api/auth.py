"""
Authentication utilities for WebApp.
"""

import hmac
import hashlib
import json
from urllib.parse import parse_qsl, unquote
from typing import Optional
from fastapi import HTTPException, Header

from config.settings import settings


def verify_telegram_webapp(init_data: str) -> dict:
    """
    Проверяет подлинность данных от Telegram WebApp.

    Args:
        init_data: строка initData от Telegram WebApp

    Returns:
        Распарсенные данные пользователя

    Raises:
        HTTPException: если подпись неверна
    """
    # Парсим данные
    parsed = dict(parse_qsl(init_data))

    # Извлекаем hash
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    # Создаём data-check-string
    data_check_arr = [f"{k}={v}" for k, v in sorted(parsed.items())]
    data_check_string = "\n".join(data_check_arr)

    # Вычисляем секретный ключ
    secret_key = hmac.new(
        "WebAppData".encode(),
        settings.TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    # Вычисляем hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    # Проверяем
    if calculated_hash != received_hash:
        raise HTTPException(status_code=401, detail="Invalid hash")

    # Возвращаем данные пользователя
    user_data = json.loads(unquote(parsed.get("user", "{}")))

    return {
        "user_id": user_data.get("id"),
        "username": user_data.get("username"),
        "first_name": user_data.get("first_name"),
    }


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> dict:
    """Dependency для получения текущего пользователя."""
    # Попробовать Basic Auth для админов
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        # Проверить админский токен
        if hasattr(settings, 'ADMIN_TOKEN') and token == settings.ADMIN_TOKEN:
            # Вернуть данные для админа
            return {
                "user_id": getattr(settings, 'ADMIN_TELEGRAM_ID', 65876198),
                "username": "admin",
                "first_name": "Admin",
            }

    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Not authorized")

    return verify_telegram_webapp(x_telegram_init_data)
