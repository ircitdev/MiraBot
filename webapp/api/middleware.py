"""
Middleware и dependencies для проверки прав доступа администраторов.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.repositories.admin_user import AdminUserRepository
from webapp.api.auth import get_current_user


security = HTTPBearer(auto_error=False)


async def get_current_admin(
    request: Request,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency для проверки что текущий пользователь - администратор или модератор.

    Args:
        request: FastAPI request object
        current_user: Данные текущего пользователя из Telegram

    Returns:
        dict с данными админа: {
            "telegram_id": int,
            "username": str,
            "admin_user": AdminUser,  # объект из БД
            "role": str,  # 'admin' или 'moderator'
        }

    Raises:
        HTTPException 403: Если пользователь не является админом/модератором
    """
    telegram_id = current_user.get("user_id")

    if not telegram_id:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )

    # Проверяем права в базе данных
    repo = AdminUserRepository()
    admin_user = await repo.get_by_telegram_id(telegram_id)

    if not admin_user:
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён. У вас нет прав администратора."
        )

    if not admin_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Ваш аккаунт администратора деактивирован."
        )

    # Обновляем время последнего входа
    await repo.update_last_login(admin_user.id)

    return {
        "telegram_id": telegram_id,
        "username": current_user.get("username"),
        "first_name": current_user.get("first_name"),
        "admin_user": admin_user,
        "role": admin_user.role,
        "admin_id": admin_user.id,
    }


async def require_admin_role(
    admin_data: dict = Depends(get_current_admin)
) -> dict:
    """
    Dependency для проверки что пользователь имеет роль 'admin' (не просто модератор).

    Args:
        admin_data: Данные администратора из get_current_admin

    Returns:
        Те же данные админа

    Raises:
        HTTPException 403: Если роль не 'admin'
    """
    if admin_data["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Требуются права администратора. У вас роль модератора."
        )

    return admin_data


async def get_admin_or_none(
    request: Request,
    current_user: dict = Depends(get_current_user)
) -> Optional[dict]:
    """
    Dependency для опциональной проверки прав администратора.
    Возвращает данные админа или None, но НЕ выбрасывает исключение.

    Используется для эндпоинтов, которые доступны всем, но с расширенными
    правами для администраторов.

    Args:
        request: FastAPI request object
        current_user: Данные текущего пользователя

    Returns:
        dict с данными админа или None
    """
    telegram_id = current_user.get("user_id")

    if not telegram_id:
        return None

    repo = AdminUserRepository()
    admin_user = await repo.get_by_telegram_id(telegram_id)

    if not admin_user or not admin_user.is_active:
        return None

    # Обновляем время последнего входа
    await repo.update_last_login(admin_user.id)

    return {
        "telegram_id": telegram_id,
        "username": current_user.get("username"),
        "first_name": current_user.get("first_name"),
        "admin_user": admin_user,
        "role": admin_user.role,
        "admin_id": admin_user.id,
    }


def check_permission(
    admin_data: dict,
    required_role: str = "moderator"
) -> bool:
    """
    Утилита для проверки прав доступа.

    Args:
        admin_data: Данные администратора
        required_role: Требуемая роль ('admin' или 'moderator')

    Returns:
        True если есть права, False иначе
    """
    if not admin_data or not admin_data.get("admin_user"):
        return False

    admin_user = admin_data["admin_user"]

    # Админ имеет все права
    if admin_user.role == "admin":
        return True

    # Модератор имеет права только если требуется роль модератора
    if required_role == "moderator" and admin_user.role == "moderator":
        return True

    return False
