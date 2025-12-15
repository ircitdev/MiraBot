"""
Репозиторий для работы с follow-ups (обещания и планы пользователя).
"""

from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, and_, or_
from loguru import logger

from database.session import get_session_context
from database.models import UserFollowUp


class FollowUpRepository:
    """Репозиторий для работы с follow-ups."""

    async def create(
        self,
        user_id: int,
        action: str,
        followup_date: datetime,
        context: Optional[str] = None,
        category: Optional[str] = None,
        scheduled_date: Optional[datetime] = None,
        priority: str = "medium",
        message_id: Optional[int] = None,
    ) -> UserFollowUp:
        """
        Создает новый follow-up.

        Args:
            user_id: ID пользователя
            action: Что пользователь планирует/обещал
            followup_date: Когда спросить "Как прошло?"
            context: Контекст (почему важно)
            category: Категория действия
            scheduled_date: Когда планировалось выполнить
            priority: Приоритет (low/medium/high/urgent)
            message_id: ID сообщения где упоминалось

        Returns:
            Созданный объект UserFollowUp
        """
        async with get_session_context() as session:
            followup = UserFollowUp(
                user_id=user_id,
                action=action,
                followup_date=followup_date,
                context=context,
                category=category,
                scheduled_date=scheduled_date,
                priority=priority,
                message_id=message_id,
                status="pending",
            )

            session.add(followup)
            await session.commit()
            await session.refresh(followup)

            logger.info(
                f"Created follow-up {followup.id} for user {user_id}: '{action[:50]}...' "
                f"(followup on {followup_date.date()})"
            )
            return followup

    async def get(self, followup_id: int) -> Optional[UserFollowUp]:
        """Получает follow-up по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFollowUp).where(UserFollowUp.id == followup_id)
            )
            return result.scalars().first()

    async def get_pending_followups(
        self,
        user_id: int,
        limit: Optional[int] = None,
    ) -> List[UserFollowUp]:
        """
        Получает все pending follow-ups пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество

        Returns:
            Список pending follow-ups
        """
        async with get_session_context() as session:
            query = select(UserFollowUp).where(
                and_(
                    UserFollowUp.user_id == user_id,
                    UserFollowUp.status == "pending",
                )
            ).order_by(UserFollowUp.followup_date.asc())

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_followups_due(
        self,
        limit: Optional[int] = None,
    ) -> List[UserFollowUp]:
        """
        Получает все follow-ups у которых пришло время для вопроса.

        Args:
            limit: Максимальное количество

        Returns:
            Список follow-ups готовых к отправке
        """
        async with get_session_context() as session:
            now = datetime.utcnow()

            query = select(UserFollowUp).where(
                and_(
                    UserFollowUp.status == "pending",
                    UserFollowUp.followup_date <= now,
                )
            ).order_by(UserFollowUp.priority.desc(), UserFollowUp.followup_date.asc())

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_by_date_range(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> List[UserFollowUp]:
        """Получает follow-ups в диапазоне дат."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFollowUp).where(
                    and_(
                        UserFollowUp.user_id == user_id,
                        UserFollowUp.created_at >= start_date,
                        UserFollowUp.created_at <= end_date,
                    )
                ).order_by(UserFollowUp.created_at.desc())
            )
            return list(result.scalars().all())

    async def mark_as_asked(self, followup_id: int) -> Optional[UserFollowUp]:
        """
        Отмечает follow-up как "задан вопрос".

        Args:
            followup_id: ID follow-up

        Returns:
            Обновленный объект UserFollowUp
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFollowUp).where(UserFollowUp.id == followup_id)
            )
            followup = result.scalars().first()

            if not followup:
                logger.warning(f"Follow-up {followup_id} not found")
                return None

            followup.status = "asked"
            followup.asked_at = datetime.utcnow()

            await session.commit()
            await session.refresh(followup)

            logger.info(f"Marked follow-up {followup_id} as asked")
            return followup

    async def mark_as_completed(
        self,
        followup_id: int,
        outcome: Optional[str] = None,
        outcome_sentiment: Optional[str] = None,
    ) -> Optional[UserFollowUp]:
        """
        Отмечает follow-up как выполненный с результатом.

        Args:
            followup_id: ID follow-up
            outcome: Что произошло в итоге
            outcome_sentiment: Оценка результата (positive/negative/neutral/mixed)

        Returns:
            Обновленный объект UserFollowUp
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFollowUp).where(UserFollowUp.id == followup_id)
            )
            followup = result.scalars().first()

            if not followup:
                logger.warning(f"Follow-up {followup_id} not found")
                return None

            followup.status = "completed"
            followup.completed_at = datetime.utcnow()
            if outcome:
                followup.outcome = outcome
            if outcome_sentiment:
                followup.outcome_sentiment = outcome_sentiment

            await session.commit()
            await session.refresh(followup)

            logger.info(
                f"Marked follow-up {followup_id} as completed with sentiment: {outcome_sentiment}"
            )
            return followup

    async def postpone(
        self,
        followup_id: int,
        new_followup_date: datetime,
    ) -> Optional[UserFollowUp]:
        """
        Откладывает follow-up на другую дату.

        Args:
            followup_id: ID follow-up
            new_followup_date: Новая дата для вопроса

        Returns:
            Обновленный объект UserFollowUp
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFollowUp).where(UserFollowUp.id == followup_id)
            )
            followup = result.scalars().first()

            if not followup:
                logger.warning(f"Follow-up {followup_id} not found")
                return None

            old_date = followup.followup_date
            followup.status = "postponed"
            followup.followup_date = new_followup_date

            # Возвращаем в pending статус для будущего follow-up
            followup.status = "pending"

            await session.commit()
            await session.refresh(followup)

            logger.info(
                f"Postponed follow-up {followup_id} from {old_date.date()} to {new_followup_date.date()}"
            )
            return followup

    async def cancel(self, followup_id: int) -> Optional[UserFollowUp]:
        """
        Отменяет follow-up.

        Args:
            followup_id: ID follow-up

        Returns:
            Обновленный объект UserFollowUp
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFollowUp).where(UserFollowUp.id == followup_id)
            )
            followup = result.scalars().first()

            if not followup:
                logger.warning(f"Follow-up {followup_id} not found")
                return None

            followup.status = "cancelled"

            await session.commit()
            await session.refresh(followup)

            logger.info(f"Cancelled follow-up {followup_id}")
            return followup

    async def get_recent_outcomes(
        self,
        user_id: int,
        days: int = 7,
        limit: int = 10,
    ) -> List[UserFollowUp]:
        """
        Получает недавние завершенные follow-ups с результатами.

        Args:
            user_id: ID пользователя
            days: За сколько дней смотреть
            limit: Максимальное количество

        Returns:
            Список completed follow-ups с outcomes
        """
        async with get_session_context() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            result = await session.execute(
                select(UserFollowUp).where(
                    and_(
                        UserFollowUp.user_id == user_id,
                        UserFollowUp.status == "completed",
                        UserFollowUp.completed_at >= cutoff_date,
                        UserFollowUp.outcome.isnot(None),
                    )
                ).order_by(UserFollowUp.completed_at.desc()).limit(limit)
            )
            return list(result.scalars().all())


# Глобальный экземпляр
followup_repo = FollowUpRepository()
