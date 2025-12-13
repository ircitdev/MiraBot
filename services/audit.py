"""
Audit service.
Логирование действий администраторов.
"""

from datetime import datetime
from typing import Optional, Any, Dict
from loguru import logger

from database.session import async_session
from database.models import AdminLog
from sqlalchemy import select, desc


class AuditService:
    """Сервис аудита действий админов."""

    # Типы действий
    ACTION_VIEW_USERS = "view_users"
    ACTION_VIEW_STATS = "view_stats"
    ACTION_VIEW_REFERRALS = "view_referrals"
    ACTION_VIEW_USER_DETAIL = "view_user_detail"
    ACTION_GIVE_PREMIUM = "give_premium"
    ACTION_EXTEND_PREMIUM = "extend_premium"
    ACTION_BLOCK_USER = "block_user"
    ACTION_UNBLOCK_USER = "unblock_user"
    ACTION_ADMIN_LOGIN = "admin_login"
    ACTION_VIEW_BLOCKED = "view_blocked"

    async def log_action(
        self,
        admin_telegram_id: int,
        action: str,
        target_user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Записывает действие админа в лог.

        Args:
            admin_telegram_id: Telegram ID админа
            action: Тип действия
            target_user_id: Telegram ID целевого пользователя (если есть)
            details: Дополнительные детали
        """
        try:
            async with async_session() as session:
                log_entry = AdminLog(
                    admin_id=admin_telegram_id,
                    action=action,
                    target_user_id=target_user_id,
                    details=details or {},
                )
                session.add(log_entry)
                await session.commit()

                logger.info(
                    f"Admin audit: {action} by {admin_telegram_id}"
                    + (f" on user {target_user_id}" if target_user_id else "")
                )
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")

    async def log_give_premium(
        self,
        admin_telegram_id: int,
        target_telegram_id: int,
        days: int,
        is_extension: bool = False,
    ) -> None:
        """Логирует выдачу/продление премиума."""
        action = self.ACTION_EXTEND_PREMIUM if is_extension else self.ACTION_GIVE_PREMIUM
        await self.log_action(
            admin_telegram_id=admin_telegram_id,
            action=action,
            target_user_id=target_telegram_id,
            details={
                "days": days,
                "is_extension": is_extension,
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def log_view_users(self, admin_telegram_id: int, page: int = 1) -> None:
        """Логирует просмотр списка пользователей."""
        await self.log_action(
            admin_telegram_id=admin_telegram_id,
            action=self.ACTION_VIEW_USERS,
            details={"page": page},
        )

    async def log_view_stats(self, admin_telegram_id: int) -> None:
        """Логирует просмотр статистики."""
        await self.log_action(
            admin_telegram_id=admin_telegram_id,
            action=self.ACTION_VIEW_STATS,
        )

    async def log_view_user_detail(
        self,
        admin_telegram_id: int,
        target_telegram_id: int,
    ) -> None:
        """Логирует просмотр детальной информации о пользователе."""
        await self.log_action(
            admin_telegram_id=admin_telegram_id,
            action=self.ACTION_VIEW_USER_DETAIL,
            target_user_id=target_telegram_id,
        )

    async def get_recent_logs(self, limit: int = 50) -> list:
        """
        Получает последние записи аудита.

        Args:
            limit: Максимальное количество записей

        Returns:
            Список записей аудита
        """
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(AdminLog)
                    .order_by(desc(AdminLog.created_at))
                    .limit(limit)
                )
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get audit logs: {e}")
            return []

    async def get_logs_by_admin(
        self,
        admin_telegram_id: int,
        limit: int = 50,
    ) -> list:
        """Получает логи конкретного админа."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(AdminLog)
                    .where(AdminLog.admin_id == admin_telegram_id)
                    .order_by(desc(AdminLog.created_at))
                    .limit(limit)
                )
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get admin logs: {e}")
            return []

    async def get_logs_for_user(
        self,
        target_telegram_id: int,
        limit: int = 50,
    ) -> list:
        """Получает логи действий над конкретным пользователем."""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(AdminLog)
                    .where(AdminLog.target_user_id == target_telegram_id)
                    .order_by(desc(AdminLog.created_at))
                    .limit(limit)
                )
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get user audit logs: {e}")
            return []

    async def log_block_user(
        self,
        admin_telegram_id: int,
        target_telegram_id: int,
        reason: Optional[str] = None,
    ) -> None:
        """Логирует блокировку пользователя."""
        await self.log_action(
            admin_telegram_id=admin_telegram_id,
            action=self.ACTION_BLOCK_USER,
            target_user_id=target_telegram_id,
            details={
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def log_unblock_user(
        self,
        admin_telegram_id: int,
        target_telegram_id: int,
    ) -> None:
        """Логирует разблокировку пользователя."""
        await self.log_action(
            admin_telegram_id=admin_telegram_id,
            action=self.ACTION_UNBLOCK_USER,
            target_user_id=target_telegram_id,
            details={
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def log_view_blocked(self, admin_telegram_id: int, page: int = 1) -> None:
        """Логирует просмотр списка заблокированных."""
        await self.log_action(
            admin_telegram_id=admin_telegram_id,
            action=self.ACTION_VIEW_BLOCKED,
            details={"page": page},
        )


# Глобальный экземпляр
audit_service = AuditService()
