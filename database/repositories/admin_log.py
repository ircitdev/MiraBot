"""
AdminLog repository.
CRUD операции для логов действий администраторов.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import AdminLog


class AdminLogRepository:
    """Репозиторий для работы с логами действий администраторов."""

    async def create(
        self,
        admin_user_id: int,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AdminLog:
        """
        Создать запись в логе.

        Args:
            admin_user_id: ID администратора
            action: Действие (напр. 'user_block', 'subscription_grant')
            resource_type: Тип ресурса ('user', 'subscription', 'message')
            resource_id: ID ресурса
            details: Дополнительные данные (JSON)
            ip_address: IP адрес
            user_agent: User Agent браузера
            success: Успешно ли выполнено
            error_message: Сообщение об ошибке (если success=False)

        Returns:
            Созданный AdminLog
        """
        async with get_session_context() as session:
            log = AdminLog(
                admin_user_id=admin_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                error_message=error_message,
            )

            session.add(log)
            await session.commit()
            await session.refresh(log)

            return log

    async def get(self, log_id: int) -> Optional[AdminLog]:
        """Получить лог по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminLog).where(AdminLog.id == log_id)
            )
            return result.scalar_one_or_none()

    async def list_logs(
        self,
        admin_user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        success: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AdminLog]:
        """
        Получить список логов с фильтрацией.

        Args:
            admin_user_id: Фильтр по админу
            action: Фильтр по действию
            resource_type: Фильтр по типу ресурса
            resource_id: Фильтр по ID ресурса
            success: Фильтр по успешности
            from_date: Начало периода
            to_date: Конец периода
            limit: Максимальное количество
            offset: Смещение

        Returns:
            Список AdminLog
        """
        async with get_session_context() as session:
            query = select(AdminLog)

            # Применяем фильтры
            if admin_user_id is not None:
                query = query.where(AdminLog.admin_user_id == admin_user_id)

            if action is not None:
                query = query.where(AdminLog.action == action)

            if resource_type is not None:
                query = query.where(AdminLog.resource_type == resource_type)

            if resource_id is not None:
                query = query.where(AdminLog.resource_id == resource_id)

            if success is not None:
                query = query.where(AdminLog.success == success)

            if from_date is not None:
                query = query.where(AdminLog.created_at >= from_date)

            if to_date is not None:
                query = query.where(AdminLog.created_at <= to_date)

            # Сортировка и пагинация
            query = query.order_by(AdminLog.created_at.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def count_logs(
        self,
        admin_user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        success: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> int:
        """
        Подсчитать количество логов с фильтрацией.

        Args:
            admin_user_id: Фильтр по админу
            action: Фильтр по действию
            resource_type: Фильтр по типу ресурса
            success: Фильтр по успешности
            from_date: Начало периода
            to_date: Конец периода

        Returns:
            Количество логов
        """
        async with get_session_context() as session:
            query = select(func.count(AdminLog.id))

            # Применяем фильтры
            conditions = []

            if admin_user_id is not None:
                conditions.append(AdminLog.admin_user_id == admin_user_id)

            if action is not None:
                conditions.append(AdminLog.action == action)

            if resource_type is not None:
                conditions.append(AdminLog.resource_type == resource_type)

            if success is not None:
                conditions.append(AdminLog.success == success)

            if from_date is not None:
                conditions.append(AdminLog.created_at >= from_date)

            if to_date is not None:
                conditions.append(AdminLog.created_at <= to_date)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            return result.scalar() or 0

    async def get_recent_actions(
        self,
        admin_user_id: int,
        limit: int = 10
    ) -> List[AdminLog]:
        """
        Получить недавние действия администратора.

        Args:
            admin_user_id: ID администратора
            limit: Количество записей

        Returns:
            Список последних AdminLog
        """
        return await self.list_logs(
            admin_user_id=admin_user_id,
            limit=limit,
            offset=0
        )

    async def get_actions_by_resource(
        self,
        resource_type: str,
        resource_id: int,
        limit: int = 50
    ) -> List[AdminLog]:
        """
        Получить все действия над конкретным ресурсом.

        Args:
            resource_type: Тип ресурса
            resource_id: ID ресурса
            limit: Максимальное количество

        Returns:
            Список AdminLog
        """
        return await self.list_logs(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit
        )

    async def get_failed_actions(
        self,
        admin_user_id: Optional[int] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[AdminLog]:
        """
        Получить неуспешные действия за последние N часов.

        Args:
            admin_user_id: ID администратора (опционально)
            hours: Период в часах
            limit: Максимальное количество

        Returns:
            Список неуспешных AdminLog
        """
        from_date = datetime.now() - timedelta(hours=hours)

        return await self.list_logs(
            admin_user_id=admin_user_id,
            success=False,
            from_date=from_date,
            limit=limit
        )
