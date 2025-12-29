"""
Декораторы для автоматического логирования действий администраторов.
"""

import functools
import traceback
from typing import Optional, Dict, Any, Callable
from fastapi import Request

from database.repositories.admin_log import AdminLogRepository


def log_admin_action(
    action: str,
    resource_type: Optional[str] = None,
    extract_resource_id: Optional[Callable] = None,
):
    """
    Декоратор для автоматического логирования действий администраторов.

    Использование:
        @router.post("/users/{user_id}/block")
        @log_admin_action(
            action="user_block",
            resource_type="user",
            extract_resource_id=lambda kwargs: kwargs.get("user_id")
        )
        async def block_user(
            user_id: int,
            admin_data: dict = Depends(get_current_admin)
        ):
            # ... код блокировки ...
            return {"success": True}

    Args:
        action: Название действия (например, 'user_block', 'subscription_grant')
        resource_type: Тип ресурса ('user', 'subscription', 'message', и т.д.)
        extract_resource_id: Функция для извлечения resource_id из аргументов

    Returns:
        Декоратор функции
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем данные админа из kwargs
            admin_data = kwargs.get("admin_data")
            request: Optional[Request] = kwargs.get("request")

            # Извлекаем resource_id если указана функция
            resource_id = None
            if extract_resource_id:
                try:
                    resource_id = extract_resource_id(kwargs)
                except Exception:
                    pass

            # Извлекаем IP и User-Agent из request
            ip_address = None
            user_agent = None
            if request:
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

            # Выполняем функцию
            success = True
            error_message = None
            result = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                # Получаем полный traceback
                error_message = f"{str(e)}\n\n{traceback.format_exc()}"
                raise
            finally:
                # Логируем действие (даже если была ошибка)
                if admin_data and admin_data.get("admin_id"):
                    try:
                        repo = AdminLogRepository()

                        # Собираем детали
                        details = {}
                        if result and isinstance(result, dict):
                            # Добавляем результат (но не весь, только ключевые поля)
                            if "success" in result:
                                details["success"] = result["success"]
                            if "message" in result:
                                details["message"] = result["message"]

                        # Добавляем параметры вызова (без чувствительных данных)
                        safe_kwargs = {
                            k: v for k, v in kwargs.items()
                            if k not in ["admin_data", "request", "password", "token"]
                            and not k.startswith("_")
                        }
                        if safe_kwargs:
                            details["params"] = safe_kwargs

                        await repo.create(
                            admin_user_id=admin_data["admin_id"],
                            action=action,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            details=details if details else None,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            success=success,
                            error_message=error_message[:1000] if error_message else None,
                        )
                    except Exception as log_error:
                        # Если не удалось залогировать - просто игнорируем
                        # Не хотим ломать основную функциональность из-за логирования
                        print(f"Failed to log admin action: {log_error}")

        return wrapper
    return decorator


def log_critical_action(action: str, resource_type: Optional[str] = None):
    """
    Декоратор для логирования критических действий (удаление, блокировка и т.д.).

    Более строгая версия log_admin_action - требует обязательного логирования
    и выбрасывает ошибку если логирование не удалось.

    Использование:
        @router.delete("/users/{user_id}")
        @log_critical_action(action="user_delete", resource_type="user")
        async def delete_user(
            user_id: int,
            admin_data: dict = Depends(get_current_admin)
        ):
            # ... код удаления ...
            return {"success": True}

    Args:
        action: Название критического действия
        resource_type: Тип ресурса

    Returns:
        Декоратор функции
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            admin_data = kwargs.get("admin_data")
            request: Optional[Request] = kwargs.get("request")

            if not admin_data or not admin_data.get("admin_id"):
                raise Exception("Critical action requires admin authentication")

            # Извлекаем resource_id из kwargs (обычно это первый путь параметр)
            resource_id = None
            for key, value in kwargs.items():
                if key.endswith("_id") and isinstance(value, int):
                    resource_id = value
                    break

            # Извлекаем IP и User-Agent
            ip_address = None
            user_agent = None
            if request:
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("user-agent")

            # Логируем ПЕРЕД выполнением (для критических действий)
            repo = AdminLogRepository()

            # Создаём предварительную запись
            details = {
                "status": "started",
                "params": {k: v for k, v in kwargs.items() if k not in ["admin_data", "request"]}
            }

            log_entry = await repo.create(
                admin_user_id=admin_data["admin_id"],
                action=f"{action}_attempt",
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,  # Пока не выполнено
            )

            # Выполняем действие
            success = True
            error_message = None
            result = None

            try:
                result = await func(*args, **kwargs)

                # Обновляем лог - действие успешно
                details["status"] = "completed"
                if result and isinstance(result, dict):
                    details["result"] = {
                        k: v for k, v in result.items()
                        if k in ["success", "message", "affected_rows"]
                    }

                await repo.create(
                    admin_user_id=admin_data["admin_id"],
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=details,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True,
                )

                return result

            except Exception as e:
                success = False
                error_message = f"{str(e)}\n\n{traceback.format_exc()}"

                # Логируем неудачу
                details["status"] = "failed"
                details["error"] = str(e)

                await repo.create(
                    admin_user_id=admin_data["admin_id"],
                    action=f"{action}_failed",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=details,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message=error_message[:1000],
                )

                raise

        return wrapper
    return decorator
