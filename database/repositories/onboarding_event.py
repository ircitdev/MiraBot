"""
Onboarding Event repository.
Логирование и получение событий онбординга пользователей.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func
from loguru import logger

from database.session import get_session_context
from database.models import OnboardingEvent


class OnboardingEventRepository:
    """Репозиторий для работы с событиями онбординга."""

    async def log_event(
        self,
        user_id: int,
        event_name: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> OnboardingEvent:
        """
        Записать событие онбординга.

        Args:
            user_id: ID пользователя
            event_name: Название события (например, 'onboarding_started')
            event_data: Дополнительные данные события в формате JSON

        Returns:
            Созданное событие OnboardingEvent
        """
        async with get_session_context() as session:
            event = OnboardingEvent(
                user_id=user_id,
                event_name=event_name,
                event_data=event_data or {}
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            logger.info(f"Logged onboarding event: user_id={user_id}, event={event_name}")
            return event

    async def get_user_events(
        self,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[OnboardingEvent]:
        """
        Получить все события онбординга для пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество событий (по умолчанию без лимита)

        Returns:
            Список событий, отсортированных по времени (от новых к старым)
        """
        async with get_session_context() as session:
            query = (
                select(OnboardingEvent)
                .where(OnboardingEvent.user_id == user_id)
                .order_by(OnboardingEvent.created_at.desc())
            )

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_event_by_name(
        self,
        user_id: int,
        event_name: str
    ) -> Optional[OnboardingEvent]:
        """
        Получить последнее событие определённого типа для пользователя.

        Args:
            user_id: ID пользователя
            event_name: Название события

        Returns:
            Событие или None, если не найдено
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(OnboardingEvent)
                .where(
                    OnboardingEvent.user_id == user_id,
                    OnboardingEvent.event_name == event_name
                )
                .order_by(OnboardingEvent.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def has_completed_onboarding(self, user_id: int) -> bool:
        """
        Проверить, завершил ли пользователь онбординг.

        Args:
            user_id: ID пользователя

        Returns:
            True если есть событие 'onboarding_completed', иначе False
        """
        event = await self.get_event_by_name(user_id, "onboarding_completed")
        return event is not None

    async def get_onboarding_funnel_stats(self) -> Dict[str, int]:
        """
        Получить статистику воронки онбординга (сколько пользователей прошло каждый шаг).

        Returns:
            Словарь с количеством пользователей на каждом этапе:
            {
                "onboarding_started": 100,
                "name_confirmed": 85,
                "problem_selected": 70,
                ...
            }
        """
        async with get_session_context() as session:
            # Получаем количество уникальных пользователей по каждому событию
            result = await session.execute(
                select(
                    OnboardingEvent.event_name,
                    func.count(func.distinct(OnboardingEvent.user_id)).label("user_count")
                )
                .group_by(OnboardingEvent.event_name)
            )

            stats = {row.event_name: row.user_count for row in result.all()}
            return stats

    async def get_dropoff_points(self) -> List[Dict[str, Any]]:
        """
        Определить точки отсева в онбординге (где пользователи чаще всего бросают).

        Returns:
            Список этапов с процентом отсева:
            [
                {
                    "step": "name_entered",
                    "reached": 100,
                    "completed_next": 85,
                    "dropoff_rate": 15.0
                },
                ...
            ]
        """
        funnel_stats = await self.get_onboarding_funnel_stats()

        # Определяем последовательность шагов онбординга
        steps = [
            "onboarding_started",
            "name_entered",
            "name_confirmed",
            "problem_selected",
            "social_portrait_entered",
            "family_status_selected",
            "onboarding_completed"
        ]

        dropoff_data = []

        for i in range(len(steps) - 1):
            current_step = steps[i]
            next_step = steps[i + 1]

            current_count = funnel_stats.get(current_step, 0)
            next_count = funnel_stats.get(next_step, 0)

            if current_count > 0:
                dropoff_rate = ((current_count - next_count) / current_count) * 100
            else:
                dropoff_rate = 0

            dropoff_data.append({
                "step": current_step,
                "reached": current_count,
                "completed_next": next_count,
                "dropoff_rate": round(dropoff_rate, 2)
            })

        return dropoff_data

    async def get_ai_parsing_success_rate(self) -> Dict[str, float]:
        """
        Получить процент успешности AI-парсинга.

        Returns:
            {
                "social_portrait_success_rate": 95.5,
                "family_details_success_rate": 87.3
            }
        """
        async with get_session_context() as session:
            # Успешность парсинга социального портрета
            social_entered = await session.scalar(
                select(func.count(func.distinct(OnboardingEvent.user_id)))
                .where(OnboardingEvent.event_name == "social_portrait_entered")
            )

            social_parsed = await session.scalar(
                select(func.count(func.distinct(OnboardingEvent.user_id)))
                .where(OnboardingEvent.event_name == "social_portrait_parsed")
            )

            # Успешность парсинга семейных данных
            family_entered = await session.scalar(
                select(func.count(func.distinct(OnboardingEvent.user_id)))
                .where(OnboardingEvent.event_name == "family_details_entered")
            )

            family_parsed = await session.scalar(
                select(func.count(func.distinct(OnboardingEvent.user_id)))
                .where(OnboardingEvent.event_name == "family_details_parsed")
            )

            social_rate = (social_parsed / social_entered * 100) if social_entered > 0 else 0
            family_rate = (family_parsed / family_entered * 100) if family_entered > 0 else 0

            return {
                "social_portrait_success_rate": round(social_rate, 2),
                "family_details_success_rate": round(family_rate, 2)
            }

    async def delete_user_events(self, user_id: int) -> int:
        """
        Удалить все события онбординга для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество удалённых событий
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(OnboardingEvent).where(OnboardingEvent.user_id == user_id)
            )
            events = result.scalars().all()

            for event in events:
                await session.delete(event)

            await session.commit()

            count = len(events)
            logger.info(f"Deleted {count} onboarding events for user_id={user_id}")
            return count
