"""
UserReport repository.
CRUD операции для AI-отчётов о пользователях.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import UserReport


class UserReportRepository:
    """Репозиторий для работы с AI-отчётами пользователей."""

    async def create(
        self,
        telegram_id: int,
        content: str,
        created_by: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None,
    ) -> UserReport:
        """
        Создать новый отчёт.

        Args:
            telegram_id: Telegram ID пользователя
            content: Текст AI-сводки
            created_by: Telegram ID создателя (администратора)
            tokens_used: Количество использованных токенов
            cost_usd: Стоимость в USD

        Returns:
            Созданный UserReport
        """
        async with get_session_context() as session:
            report = UserReport(
                telegram_id=telegram_id,
                content=content,
                created_by=created_by,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
            )

            session.add(report)
            await session.commit()
            await session.refresh(report)

            return report

    async def get(self, report_id: int) -> Optional[UserReport]:
        """Получить отчёт по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserReport).where(UserReport.id == report_id)
            )
            return result.scalar_one_or_none()

    async def list_by_user(
        self,
        telegram_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserReport]:
        """
        Получить все отчёты пользователя.

        Args:
            telegram_id: Telegram ID пользователя
            limit: Максимальное количество записей
            offset: Смещение

        Returns:
            Список UserReport, отсортированный по дате (новые первыми)
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserReport)
                .where(UserReport.telegram_id == telegram_id)
                .order_by(desc(UserReport.created_at))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    async def count_by_user(self, telegram_id: int) -> int:
        """Подсчитать количество отчётов пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserReport).where(UserReport.telegram_id == telegram_id)
            )
            return len(list(result.scalars().all()))

    async def delete(self, report_id: int) -> bool:
        """
        Удалить отчёт.

        Args:
            report_id: ID отчёта

        Returns:
            True если удалён, False если не найден
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserReport).where(UserReport.id == report_id)
            )
            report = result.scalar_one_or_none()

            if not report:
                return False

            await session.delete(report)
            await session.commit()

            return True
