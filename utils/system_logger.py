"""
System Logger utility for automatic event logging.
Логирует события пользователей в admin_logs от имени системного администратора.
"""

from typing import Optional, Dict, Any
from database.repositories.admin_log import AdminLogRepository
from database.repositories.admin_user import AdminUserRepository


class SystemLogger:
    """Логгер системных событий в admin_logs."""

    def __init__(self):
        self.admin_log_repo = AdminLogRepository()
        self.admin_user_repo = AdminUserRepository()
        self._system_admin_id = None

    async def _get_system_admin_id(self) -> int:
        """Получить ID системного администратора."""
        if self._system_admin_id is None:
            # Ищем системного админа с telegram_id = 0
            system_admin = await self.admin_user_repo.get_by_telegram_id(0)
            if system_admin:
                self._system_admin_id = system_admin.id
            else:
                raise RuntimeError("System admin user not found. Run migrations first.")
        return self._system_admin_id

    async def log_event(
        self,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Логирует системное событие.

        Args:
            action: Действие (напр. 'user_onboarding_completed')
            resource_type: Тип ресурса ('user', 'file', etc.)
            resource_id: ID ресурса
            details: Дополнительные данные
        """
        try:
            system_admin_id = await self._get_system_admin_id()
            await self.admin_log_repo.create(
                admin_user_id=system_admin_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address="127.0.0.1",  # System internal
                user_agent="MiraBot/System",
                success=True,
            )
        except Exception as e:
            # Логируем ошибку, но не прерываем основной процесс
            print(f"Failed to log system event: {e}")

    # === Онбординг и рефералы ===

    async def log_user_onboarding_completed(
        self,
        user_id: int,
        telegram_id: int,
        username: Optional[str],
        first_name: str,
        referrer_telegram_id: Optional[int] = None,
        referrer_username: Optional[str] = None,
    ) -> None:
        """Логирует завершение онбординга пользователем."""
        details = {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
        }

        if referrer_telegram_id:
            details["referrer"] = {
                "telegram_id": referrer_telegram_id,
                "username": referrer_username,
            }
            action = "user_onboarding_with_referral"
        else:
            action = "user_onboarding_completed"

        await self.log_event(
            action=action,
            resource_type="user",
            resource_id=user_id,
            details=details,
        )

    # === Первые сообщения ===

    async def log_first_voice_message(
        self,
        user_id: int,
        telegram_id: int,
        username: Optional[str],
        duration: Optional[int] = None,
    ) -> None:
        """Логирует первое голосовое сообщение пользователя."""
        details = {
            "telegram_id": telegram_id,
            "username": username,
            "duration_seconds": duration,
        }

        await self.log_event(
            action="user_first_voice_message",
            resource_type="user",
            resource_id=user_id,
            details=details,
        )

    async def log_first_photo_message(
        self,
        user_id: int,
        telegram_id: int,
        username: Optional[str],
    ) -> None:
        """Логирует первое сообщение с изображением/фото."""
        details = {
            "telegram_id": telegram_id,
            "username": username,
        }

        await self.log_event(
            action="user_first_photo_message",
            resource_type="user",
            resource_id=user_id,
            details=details,
        )

    # === Вехи по количеству сообщений ===

    async def log_message_milestone(
        self,
        user_id: int,
        telegram_id: int,
        username: Optional[str],
        milestone: int,  # 50, 100, 300, 1000
        total_messages: int,
    ) -> None:
        """Логирует достижение вехи по количеству сообщений."""
        details = {
            "telegram_id": telegram_id,
            "username": username,
            "milestone": milestone,
            "total_messages": total_messages,
        }

        await self.log_event(
            action=f"user_messages_milestone_{milestone}",
            resource_type="user",
            resource_id=user_id,
            details=details,
        )

    # === Неактивность ===

    async def log_user_inactive(
        self,
        user_id: int,
        telegram_id: int,
        username: Optional[str],
        total_messages: int,
        days_inactive: int,
    ) -> None:
        """Логирует неактивного пользователя (50+ сообщений, 5 дней неактивности)."""
        details = {
            "telegram_id": telegram_id,
            "username": username,
            "total_messages": total_messages,
            "days_inactive": days_inactive,
        }

        await self.log_event(
            action="user_inactive_warning",
            resource_type="user",
            resource_id=user_id,
            details=details,
        )

    # === Обновления файлов ===

    async def log_todo_update(
        self,
        file_path: str,
        updated_by: Optional[str] = None,
    ) -> None:
        """Логирует обновление TODO файлов."""
        details = {
            "file_path": file_path,
            "updated_by": updated_by or "system",
        }

        await self.log_event(
            action="file_todo_updated",
            resource_type="file",
            details=details,
        )

    async def log_changelog_update(
        self,
        version: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> None:
        """Логирует обновление Changelog."""
        details = {
            "version": version,
            "updated_by": updated_by or "system",
        }

        await self.log_event(
            action="file_changelog_updated",
            resource_type="file",
            details=details,
        )


# Глобальный экземпляр
system_logger = SystemLogger()
