"""
Scheduled message repository.
CRUD операции для запланированных сообщений (ритуалы).
"""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import ScheduledMessage


class ScheduledMessageRepository:
    """Репозиторий для работы с запланированными сообщениями."""
    
    async def create(
        self,
        user_id: int,
        type: str,
        scheduled_for: datetime,
        content: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> ScheduledMessage:
        """Создать запланированное сообщение."""
        async with get_session_context() as session:
            message = ScheduledMessage(
                user_id=user_id,
                type=type,
                scheduled_for=scheduled_for,
                content=content,
                context=context,
                status="pending",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            
            return message
    
    async def get(self, message_id: int) -> Optional[ScheduledMessage]:
        """Получить сообщение по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(ScheduledMessage).where(ScheduledMessage.id == message_id)
            )
            return result.scalar_one_or_none()
    
    async def get_pending(self, limit: int = 100) -> List[ScheduledMessage]:
        """Получить сообщения, готовые к отправке."""
        async with get_session_context() as session:
            result = await session.execute(
                select(ScheduledMessage).where(
                    and_(
                        ScheduledMessage.status == "pending",
                        ScheduledMessage.scheduled_for <= datetime.now()
                    )
                ).order_by(ScheduledMessage.scheduled_for).limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_by_user(
        self,
        user_id: int,
        status: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 50,
    ) -> List[ScheduledMessage]:
        """Получить сообщения пользователя."""
        async with get_session_context() as session:
            query = select(ScheduledMessage).where(
                ScheduledMessage.user_id == user_id
            )
            
            if status:
                query = query.where(ScheduledMessage.status == status)
            if type:
                query = query.where(ScheduledMessage.type == type)
            
            query = query.order_by(ScheduledMessage.scheduled_for.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def mark_sent(self, message_id: int) -> Optional[ScheduledMessage]:
        """Отметить сообщение как отправленное."""
        async with get_session_context() as session:
            result = await session.execute(
                select(ScheduledMessage).where(ScheduledMessage.id == message_id)
            )
            message = result.scalar_one_or_none()
            
            if not message:
                return None
            
            message.status = "sent"
            message.sent_at = datetime.now()
            
            await session.commit()
            await session.refresh(message)
            
            return message
    
    async def cancel(self, message_id: int) -> Optional[ScheduledMessage]:
        """Отменить сообщение."""
        async with get_session_context() as session:
            result = await session.execute(
                select(ScheduledMessage).where(ScheduledMessage.id == message_id)
            )
            message = result.scalar_one_or_none()
            
            if not message:
                return None
            
            message.status = "cancelled"
            await session.commit()
            await session.refresh(message)
            
            return message
    
    async def cancel_by_user(
        self,
        user_id: int,
        type: Optional[str] = None,
    ) -> int:
        """
        Отменить все pending сообщения пользователя.
        Возвращает количество отменённых.
        """
        async with get_session_context() as session:
            messages = await session.execute(
                select(ScheduledMessage).where(
                    and_(
                        ScheduledMessage.user_id == user_id,
                        ScheduledMessage.status == "pending"
                    )
                )
            )
            
            count = 0
            for msg in messages.scalars().all():
                if type is None or msg.type == type:
                    msg.status = "cancelled"
                    count += 1
            
            await session.commit()
            return count
    
    async def delete_old(self, days: int = 30) -> int:
        """
        Удалить старые отправленные/отменённые сообщения.
        Возвращает количество удалённых.
        """
        async with get_session_context() as session:
            cutoff = datetime.now() - timedelta(days=days)
            
            messages = await session.execute(
                select(ScheduledMessage).where(
                    and_(
                        ScheduledMessage.status.in_(["sent", "cancelled"]),
                        ScheduledMessage.created_at < cutoff
                    )
                )
            )
            
            count = 0
            for msg in messages.scalars().all():
                await session.delete(msg)
                count += 1
            
            await session.commit()
            return count
    
    async def count_pending_by_user(self, user_id: int) -> int:
        """Количество pending сообщений у пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(ScheduledMessage.id)).where(
                    and_(
                        ScheduledMessage.user_id == user_id,
                        ScheduledMessage.status == "pending"
                    )
                )
            )
            return result.scalar() or 0
