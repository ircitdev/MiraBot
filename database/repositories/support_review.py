"""
Support Review Repository.
Репозиторий для работы с отзывами пользователей.
"""

from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SupportReview, SupportUser
from database.session import get_session_context


class SupportReviewRepository:
    """Репозиторий для работы с отзывами."""

    async def create(
        self,
        username: Optional[str],
        age: Optional[int],
        about_self: Optional[str],
        review_text: str,
        permission_to_publish: bool,
        user_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> SupportReview:
        """
        Создать новый отзыв.

        Args:
            username: @username из Telegram
            age: Возраст пользователя
            about_self: О себе
            review_text: Текст отзыва
            permission_to_publish: Разрешение на публикацию
            user_id: ID пользователя (опционально)
            telegram_message_id: ID сообщения в топике #4
        """
        async with get_session_context() as session:
            review = SupportReview(
                user_id=user_id,
                username=username,
                age=age,
                about_self=about_self,
                review_text=review_text,
                permission_to_publish=permission_to_publish,
                telegram_message_id=telegram_message_id,
            )
            session.add(review)
            await session.commit()
            await session.refresh(review)
            return review

    async def get_by_id(self, review_id: int) -> Optional[SupportReview]:
        """Получить отзыв по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportReview).where(SupportReview.id == review_id)
            )
            return result.scalar_one_or_none()

    async def get_all_paginated(
        self,
        page: int = 1,
        limit: int = 20,
        permission: Optional[bool] = None,
    ) -> Tuple[List[SupportReview], int]:
        """
        Получить все отзывы с пагинацией и фильтрацией.

        Args:
            page: Номер страницы
            limit: Количество на странице
            permission: Фильтр по разрешению на публикацию (None = все)

        Returns:
            Tuple[List[SupportReview], int]: (список отзывов, общее количество)
        """
        async with get_session_context() as session:
            # Базовый запрос
            query = select(SupportReview)

            # Фильтрация по разрешению
            if permission is not None:
                query = query.where(SupportReview.permission_to_publish == permission)

            # Подсчёт общего количества
            count_query = select(func.count(SupportReview.id))
            if permission is not None:
                count_query = count_query.where(
                    SupportReview.permission_to_publish == permission
                )

            count_result = await session.execute(count_query)
            total = count_result.scalar_one()

            # Получение отзывов с пагинацией
            offset = (page - 1) * limit
            result = await session.execute(
                query.order_by(SupportReview.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            reviews = result.scalars().all()

            return list(reviews), total

    async def export_to_json(
        self,
        permission: bool = True,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Экспортировать отзывы в формате JSON для использования на лендинге.

        Args:
            permission: Только с разрешением на публикацию
            limit: Максимальное количество отзывов

        Returns:
            List[Dict]: Список отзывов в формате для лендинга
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportReview)
                .where(SupportReview.permission_to_publish == permission)
                .order_by(SupportReview.created_at.desc())
                .limit(limit)
            )
            reviews = result.scalars().all()

            # Форматируем для лендинга
            formatted_reviews = []
            for review in reviews:
                # Формируем имя
                if review.username:
                    name = review.username.lstrip('@')
                else:
                    name = "Аноним"

                if review.age:
                    name = f"{name}, {review.age} лет"

                formatted_reviews.append({
                    "name": name,
                    "about": review.about_self or "",
                    "text": review.review_text,
                    "date": review.created_at.strftime("%d.%m.%Y"),
                })

            return formatted_reviews

    async def count_all(self, permission: Optional[bool] = None) -> int:
        """
        Подсчитать общее количество отзывов.

        Args:
            permission: Фильтр по разрешению на публикацию (None = все)
        """
        async with get_session_context() as session:
            query = select(func.count(SupportReview.id))

            if permission is not None:
                query = query.where(SupportReview.permission_to_publish == permission)

            result = await session.execute(query)
            return result.scalar_one()

    async def get_recent(self, limit: int = 10) -> List[SupportReview]:
        """Получить последние отзывы."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportReview)
                .order_by(SupportReview.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
