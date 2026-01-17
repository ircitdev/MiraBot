"""
User Profile repository.
CRUD операции для профилей пользователей.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import select
from loguru import logger

from database.session import get_session_context
from database.models import UserProfile


class UserProfileRepository:
    """Репозиторий для работы с профилями пользователей."""

    async def get_profile(self, user_id: int) -> Optional[UserProfile]:
        """Получить профиль пользователя по user_id."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def get_or_create_profile(self, user_id: int) -> UserProfile:
        """
        Получить или создать профиль пользователя.
        Возвращает UserProfile.
        """
        async with get_session_context() as session:
            # Пробуем найти
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()

            if profile:
                return profile

            # Создаём новый профиль
            profile = UserProfile(user_id=user_id)
            session.add(profile)
            await session.commit()
            await session.refresh(profile)

            logger.info(f"Created new profile for user_id={user_id}")
            return profile

    async def update_profile(self, user_id: int, **kwargs) -> Optional[UserProfile]:
        """
        Обновить профиль пользователя.

        Args:
            user_id: ID пользователя
            **kwargs: Поля для обновления (age, city, occupation, partner_name, etc.)

        Returns:
            Обновлённый профиль или None
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                logger.warning(f"Profile not found for user_id={user_id}, creating new one")
                profile = UserProfile(user_id=user_id)
                session.add(profile)

            # Обновляем только переданные поля
            for key, value in kwargs.items():
                if hasattr(profile, key) and value is not None:
                    setattr(profile, key, value)

            profile.updated_at = datetime.now()
            await session.commit()
            await session.refresh(profile)

            logger.info(f"Updated profile for user_id={user_id}: {kwargs}")
            return profile

    async def delete_profile(self, user_id: int) -> bool:
        """
        Удалить профиль пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            True если профиль удалён, False если не найден
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                return False

            await session.delete(profile)
            await session.commit()

            logger.info(f"Deleted profile for user_id={user_id}")
            return True
