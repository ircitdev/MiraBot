"""
Conversation repository.
CRUD операции для сообщений и истории диалогов.
"""

from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import Message


class ConversationRepository:
    """Репозиторий для работы с историей сообщений."""
    
    async def save_message(
        self,
        user_id: int,
        role: str,
        content: str,
        tags: Optional[List[str]] = None,
        tokens_used: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        message_type: str = "text",
    ) -> Message:
        """Сохранить сообщение."""
        async with get_session_context() as session:
            message = Message(
                user_id=user_id,
                role=role,
                content=content,
                tags=tags or [],
                tokens_used=tokens_used,
                response_time_ms=response_time_ms,
                message_type=message_type,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            
            return message
    
    async def get_recent(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[Message]:
        """Получить последние сообщения пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Message)
                .where(Message.user_id == user_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            messages = list(result.scalars().all())
            # Возвращаем в хронологическом порядке
            return list(reversed(messages))
    
    async def get_paginated(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Message], int]:
        """
        Получить пагинированную историю сообщений.
        Возвращает (messages, total_count).
        """
        async with get_session_context() as session:
            # Основной запрос
            offset = (page - 1) * per_page
            query = (
                select(Message)
                .where(Message.user_id == user_id)
                .order_by(Message.created_at.desc())
                .offset(offset)
                .limit(per_page)
            )
            
            result = await session.execute(query)
            messages = list(result.scalars().all())
            
            # Подсчёт
            count_result = await session.execute(
                select(func.count(Message.id)).where(Message.user_id == user_id)
            )
            total = count_result.scalar() or 0
            
            return messages, total
    
    async def count_by_user(self, user_id: int) -> int:
        """Общее количество сообщений пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Message.id)).where(Message.user_id == user_id)
            )
            return result.scalar() or 0

    async def count_by_user_since(self, user_id: int, since: datetime) -> int:
        """Количество сообщений пользователя с определённой даты."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Message.id)).where(
                    and_(
                        Message.user_id == user_id,
                        Message.created_at >= since
                    )
                )
            )
            return result.scalar() or 0

    async def count_user_messages(self, user_id: int) -> int:
        """Количество сообщений от пользователя (только role='user')."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Message.id)).where(
                    and_(
                        Message.user_id == user_id,
                        Message.role == "user"
                    )
                )
            )
            return result.scalar() or 0
    
    async def count_sessions(self, user_id: int) -> int:
        """
        Количество сессий (дней с активностью).
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(func.distinct(func.date(Message.created_at)))).where(
                    Message.user_id == user_id
                )
            )
            return result.scalar() or 0
    
    async def avg_messages_per_session(self, user_id: int) -> float:
        """Среднее количество сообщений за сессию."""
        total_messages = await self.count_by_user(user_id)
        total_sessions = await self.count_sessions(user_id)
        
        if total_sessions == 0:
            return 0.0
        
        return round(total_messages / total_sessions, 2)
    
    async def get_top_tags(self, user_id: int, limit: int = 5) -> List[dict]:
        """Топ тегов пользователя."""
        # TODO: Реализовать для SQLite (jsonb_array_elements_text только в PostgreSQL)
        # Для SQLite временно возвращаем пустой список
        from config.settings import settings
        if settings.DATABASE_URL.startswith("sqlite"):
            return []

        async with get_session_context() as session:
            from sqlalchemy import text
            # PostgreSQL специфичный запрос для работы с JSONB массивами
            result = await session.execute(
                text("""
                SELECT tag, COUNT(*) as count
                FROM messages, jsonb_array_elements_text(tags) as tag
                WHERE user_id = :user_id
                GROUP BY tag
                ORDER BY count DESC
                LIMIT :limit
                """),
                {"user_id": user_id, "limit": limit}
            )

            return [{"tag": row[0], "count": row[1]} for row in result.fetchall()]
    
    async def count_crisis_episodes(self, user_id: int) -> int:
        """Количество кризисных эпизодов."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Message.id)).where(
                    and_(
                        Message.user_id == user_id,
                        Message.tags.contains(["crisis"])
                    )
                )
            )
            return result.scalar() or 0
    
    async def get_messages_count_since(self, since: datetime) -> int:
        """Количество сообщений с определённой даты."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Message.id)).where(
                    Message.created_at >= since
                )
            )
            return result.scalar() or 0
    
    async def get_with_tag(
        self,
        tag: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Message]:
        """Получить сообщения с определённым тегом."""
        async with get_session_context() as session:
            query = select(Message).where(
                Message.tags.contains([tag])
            )
            
            if since:
                query = query.where(Message.created_at >= since)
            
            query = query.order_by(Message.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_user_message_stats(
        self,
        user_id: int,
        since: Optional[datetime] = None,
    ) -> dict:
        """
        Получить статистику сообщений пользователя.
        Возвращает: total, text, voice за указанный период.
        """
        async with get_session_context() as session:
            base_filter = and_(
                Message.user_id == user_id,
                Message.role == "user"  # Только сообщения от пользователя
            )

            if since:
                base_filter = and_(base_filter, Message.created_at >= since)

            # Общее количество
            total_result = await session.execute(
                select(func.count(Message.id)).where(base_filter)
            )
            total = total_result.scalar() or 0

            # Текстовые
            text_result = await session.execute(
                select(func.count(Message.id)).where(
                    and_(base_filter, Message.message_type == "text")
                )
            )
            text_count = text_result.scalar() or 0

            # Голосовые
            voice_result = await session.execute(
                select(func.count(Message.id)).where(
                    and_(base_filter, Message.message_type == "voice")
                )
            )
            voice_count = voice_result.scalar() or 0

            return {
                "total": total,
                "text": text_count,
                "voice": voice_count,
            }


    async def get_last_message(
        self,
        user_id: int,
        role: Optional[str] = None,
    ) -> Optional[Message]:
        """
        Получить последнее сообщение пользователя.

        Args:
            user_id: ID пользователя
            role: Опционально фильтр по роли ('user' или 'assistant')

        Returns:
            Последнее сообщение или None
        """
        async with get_session_context() as session:
            query = select(Message).where(Message.user_id == user_id)

            if role:
                query = query.where(Message.role == role)

            query = query.order_by(Message.created_at.desc()).limit(1)

            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def delete_old_messages(
        self,
        user_id: int,
        keep_count: int = 100,
    ) -> int:
        """
        Удалить старые сообщения, оставив последние N.
        Возвращает количество удалённых.
        """
        async with get_session_context() as session:
            # Получаем ID сообщений для сохранения
            keep_query = (
                select(Message.id)
                .where(Message.user_id == user_id)
                .order_by(Message.created_at.desc())
                .limit(keep_count)
            )
            keep_result = await session.execute(keep_query)
            keep_ids = [row[0] for row in keep_result.fetchall()]
            
            if not keep_ids:
                return 0
            
            # Удаляем остальные
            delete_query = (
                Message.__table__.delete()
                .where(
                    and_(
                        Message.user_id == user_id,
                        ~Message.id.in_(keep_ids)
                    )
                )
            )
            
            result = await session.execute(delete_query)
            await session.commit()
            
            return result.rowcount
