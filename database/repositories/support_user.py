"""
Support User Repository.
Репозиторий для работы с пользователями бота технической поддержки.
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SupportUser
from database.session import get_session_context


class SupportUserRepository:
    """Репозиторий для работы с пользователями поддержки."""

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[SupportUser]:
        """Получить пользователя по Telegram ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportUser).where(SupportUser.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[SupportUser]:
        """Получить пользователя по внутреннему ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportUser).where(SupportUser.id == user_id)
            )
            return result.scalar_one_or_none()

    async def get_by_topic_id(self, topic_id: int) -> Optional[SupportUser]:
        """Получить пользователя по ID топика в супергруппе."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportUser).where(SupportUser.topic_id == topic_id)
            )
            return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        first_name: str,
        last_name: Optional[str],
        username: Optional[str],
        photo_url: Optional[str],
        topic_id: int,
    ) -> SupportUser:
        """Создать нового пользователя поддержки."""
        async with get_session_context() as session:
            user = SupportUser(
                telegram_id=telegram_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                photo_url=photo_url,
                topic_id=topic_id,
                is_bot_blocked=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def update_topic_id(self, user_id: int, topic_id: int) -> None:
        """Обновить ID топика для пользователя."""
        async with get_session_context() as session:
            await session.execute(
                update(SupportUser)
                .where(SupportUser.id == user_id)
                .values(topic_id=topic_id)
            )
            await session.commit()

    async def update_photo(self, user_id: int, photo_url: str) -> None:
        """Обновить фото пользователя."""
        async with get_session_context() as session:
            await session.execute(
                update(SupportUser)
                .where(SupportUser.id == user_id)
                .values(photo_url=photo_url)
            )
            await session.commit()

    async def mark_bot_blocked(self, user_id: int, is_blocked: bool = True) -> None:
        """Отметить, что пользователь заблокировал бота."""
        async with get_session_context() as session:
            await session.execute(
                update(SupportUser)
                .where(SupportUser.id == user_id)
                .values(is_bot_blocked=is_blocked)
            )
            await session.commit()

    async def get_all_paginated(
        self,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[SupportUser], int]:
        """
        Получить всех пользователей с пагинацией.

        Returns:
            Tuple[List[SupportUser], int]: (список пользователей, общее количество)
        """
        async with get_session_context() as session:
            # Подсчёт общего количества
            count_result = await session.execute(
                select(func.count(SupportUser.id))
            )
            total = count_result.scalar_one()

            # Получение пользователей с пагинацией
            offset = (page - 1) * limit
            result = await session.execute(
                select(SupportUser)
                .order_by(SupportUser.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            users = result.scalars().all()

            return list(users), total

    async def exists(self, telegram_id: int) -> bool:
        """Проверить, существует ли пользователь с данным Telegram ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(SupportUser.id)).where(
                    SupportUser.telegram_id == telegram_id
                )
            )
            count = result.scalar_one()
            return count > 0
