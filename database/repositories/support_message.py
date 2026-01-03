"""
Support Message Repository.
Репозиторий для работы с сообщениями в технической поддержке.
"""

from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SupportMessage
from database.session import get_session_context


class SupportMessageRepository:
    """Репозиторий для работы с сообщениями поддержки."""

    async def create(
        self,
        user_id: int,
        sender_type: str,
        message_text: Optional[str] = None,
        media_type: str = "text",
        media_file_id: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
    ) -> SupportMessage:
        """
        Создать новое сообщение.

        Args:
            user_id: ID пользователя поддержки
            sender_type: "user" или "admin"
            message_text: Текст сообщения
            media_type: Тип медиа (text, photo, video, voice, video_note, document, sticker)
            media_file_id: file_id из Telegram
            telegram_message_id: ID сообщения в Telegram
        """
        async with get_session_context() as session:
            message = SupportMessage(
                user_id=user_id,
                sender_type=sender_type,
                message_text=message_text,
                media_type=media_type,
                media_file_id=media_file_id,
                telegram_message_id=telegram_message_id,
                is_read=False,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return message

    async def get_by_user(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 50,
    ) -> Tuple[List[SupportMessage], int]:
        """
        Получить сообщения пользователя с пагинацией.

        Returns:
            Tuple[List[SupportMessage], int]: (список сообщений, общее количество)
        """
        async with get_session_context() as session:
            # Подсчёт общего количества
            count_result = await session.execute(
                select(func.count(SupportMessage.id)).where(
                    SupportMessage.user_id == user_id
                )
            )
            total = count_result.scalar_one()

            # Получение сообщений с пагинацией
            offset = (page - 1) * limit
            result = await session.execute(
                select(SupportMessage)
                .where(SupportMessage.user_id == user_id)
                .order_by(SupportMessage.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
            messages = result.scalars().all()

            return list(messages), total

    async def get_last_message_date(self, user_id: int) -> Optional[datetime]:
        """Получить дату последнего сообщения пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportMessage.created_at)
                .where(SupportMessage.user_id == user_id)
                .order_by(SupportMessage.created_at.desc())
                .limit(1)
            )
            last_date = result.scalar_one_or_none()
            return last_date

    async def get_last_message_text(self, user_id: int) -> Optional[str]:
        """Получить текст последнего сообщения пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SupportMessage.message_text)
                .where(SupportMessage.user_id == user_id)
                .order_by(SupportMessage.created_at.desc())
                .limit(1)
            )
            last_text = result.scalar_one_or_none()
            return last_text

    async def count_by_user(self, user_id: int) -> int:
        """Подсчитать количество сообщений пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(SupportMessage.id)).where(
                    SupportMessage.user_id == user_id
                )
            )
            return result.scalar_one()

    async def mark_as_read(self, message_id: int) -> None:
        """Отметить сообщение как прочитанное."""
        async with get_session_context() as session:
            await session.execute(
                update(SupportMessage)
                .where(SupportMessage.id == message_id)
                .values(is_read=True)
            )
            await session.commit()

    async def mark_user_messages_as_read(self, user_id: int, sender_type: str) -> None:
        """
        Отметить все сообщения пользователя определённого типа как прочитанные.

        Args:
            user_id: ID пользователя
            sender_type: "user" или "admin"
        """
        async with get_session_context() as session:
            await session.execute(
                update(SupportMessage)
                .where(
                    SupportMessage.user_id == user_id,
                    SupportMessage.sender_type == sender_type,
                    SupportMessage.is_read == False,
                )
                .values(is_read=True)
            )
            await session.commit()

    async def get_unread_count(self, user_id: int, sender_type: str) -> int:
        """
        Получить количество непрочитанных сообщений.

        Args:
            user_id: ID пользователя
            sender_type: "user" или "admin"
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(SupportMessage.id)).where(
                    SupportMessage.user_id == user_id,
                    SupportMessage.sender_type == sender_type,
                    SupportMessage.is_read == False,
                )
            )
            return result.scalar_one()
