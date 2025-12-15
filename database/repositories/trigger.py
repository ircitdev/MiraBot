"""
Repository для работы с триггерами пользователя.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.session import get_session_context
from database.models import UserTrigger


class TriggerRepository:
    """Репозиторий для работы с чувствительными темами (триггерами)."""

    async def create(
        self,
        user_id: int,
        topic: str,
        description: Optional[str] = None,
        severity: int = 5,
    ) -> UserTrigger:
        """
        Создает новый триггер.

        Args:
            user_id: ID пользователя
            topic: Тема триггера
            description: Описание (опционально)
            severity: Степень чувствительности (1-10)

        Returns:
            Созданный триггер
        """
        async with get_session_context() as session:
            # Проверяем, нет ли уже такого триггера
            existing = await self.get_by_topic(user_id, topic)
            if existing:
                # Обновляем существующий
                existing.severity = max(existing.severity, severity)
                existing.is_active = True
                if description:
                    existing.description = description
                existing.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(existing)
                return existing

            trigger = UserTrigger(
                user_id=user_id,
                topic=topic.lower(),  # Нормализуем к lowercase
                description=description,
                severity=severity,
            )

            session.add(trigger)
            await session.commit()
            await session.refresh(trigger)

            logger.info(f"Created trigger for user {user_id}: {topic} (severity={severity})")
            return trigger

    async def get_active_triggers(self, user_id: int) -> List[UserTrigger]:
        """
        Получает все активные триггеры пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список активных триггеров
        """
        async with get_session_context() as session:
            stmt = select(UserTrigger).where(
                and_(
                    UserTrigger.user_id == user_id,
                    UserTrigger.is_active == True
                )
            ).order_by(UserTrigger.severity.desc())

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_topic(
        self,
        user_id: int,
        topic: str
    ) -> Optional[UserTrigger]:
        """
        Получает триггер по теме.

        Args:
            user_id: ID пользователя
            topic: Тема

        Returns:
            Триггер или None
        """
        async with get_session_context() as session:
            stmt = select(UserTrigger).where(
                and_(
                    UserTrigger.user_id == user_id,
                    UserTrigger.topic == topic.lower()
                )
            )

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_last_mentioned(
        self,
        trigger_id: int,
        mentioned_at: Optional[datetime] = None
    ) -> None:
        """
        Обновляет время последнего упоминания темы.

        Args:
            trigger_id: ID триггера
            mentioned_at: Время упоминания (по умолчанию - сейчас)
        """
        if mentioned_at is None:
            mentioned_at = datetime.utcnow()

        async with get_session_context() as session:
            stmt = (
                update(UserTrigger)
                .where(UserTrigger.id == trigger_id)
                .values(last_mentioned_at=mentioned_at)
            )
            await session.execute(stmt)
            await session.commit()

    async def deactivate(self, trigger_id: int) -> None:
        """
        Деактивирует триггер.

        Args:
            trigger_id: ID триггера
        """
        async with get_session_context() as session:
            stmt = (
                update(UserTrigger)
                .where(UserTrigger.id == trigger_id)
                .values(is_active=False, updated_at=datetime.utcnow())
            )
            await session.execute(stmt)
            await session.commit()

            logger.info(f"Deactivated trigger {trigger_id}")

    async def reactivate(self, trigger_id: int) -> None:
        """
        Реактивирует триггер.

        Args:
            trigger_id: ID триггера
        """
        async with get_session_context() as session:
            stmt = (
                update(UserTrigger)
                .where(UserTrigger.id == trigger_id)
                .values(is_active=True, updated_at=datetime.utcnow())
            )
            await session.execute(stmt)
            await session.commit()

            logger.info(f"Reactivated trigger {trigger_id}")

    async def delete(self, trigger_id: int) -> None:
        """
        Удаляет триггер.

        Args:
            trigger_id: ID триггера
        """
        async with get_session_context() as session:
            stmt = select(UserTrigger).where(UserTrigger.id == trigger_id)
            result = await session.execute(stmt)
            trigger = result.scalar_one_or_none()

            if trigger:
                await session.delete(trigger)
                await session.commit()
                logger.info(f"Deleted trigger {trigger_id}")
