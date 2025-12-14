"""
Memory repository.
CRUD операции для долговременной памяти.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import MemoryEntry


class MemoryRepository:
    """Репозиторий для работы с долговременной памятью."""
    
    async def create(
        self,
        user_id: int,
        category: str,
        content: str,
        importance: int = 5,
        source_message_ids: Optional[List[int]] = None,
        expires_at: Optional[datetime] = None,
    ) -> MemoryEntry:
        """Создать запись в памяти."""
        async with get_session_context() as session:
            entry = MemoryEntry(
                user_id=user_id,
                category=category,
                content=content,
                importance=importance,
                source_message_ids=source_message_ids,
                expires_at=expires_at,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            
            return entry
    
    async def get(self, entry_id: int) -> Optional[MemoryEntry]:
        """Получить запись по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(MemoryEntry).where(MemoryEntry.id == entry_id)
            )
            return result.scalar_one_or_none()
    
    async def get_by_user(
        self,
        user_id: int,
        category: Optional[str] = None,
        min_importance: int = 0,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """Получить записи памяти пользователя."""
        async with get_session_context() as session:
            query = select(MemoryEntry).where(
                and_(
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.importance >= min_importance,
                    or_(
                        MemoryEntry.expires_at.is_(None),
                        MemoryEntry.expires_at > datetime.now()
                    )
                )
            )
            
            if category:
                query = query.where(MemoryEntry.category == category)
            
            query = query.order_by(
                MemoryEntry.importance.desc(),
                MemoryEntry.updated_at.desc()
            ).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_by_categories(
        self,
        user_id: int,
        categories: List[str],
        limit_per_category: int = 10,
    ) -> dict:
        """
        Получить записи по нескольким категориям.
        Возвращает словарь {category: [entries]}.
        """
        result = {}
        for category in categories:
            entries = await self.get_by_user(
                user_id=user_id,
                category=category,
                limit=limit_per_category,
            )
            result[category] = entries
        return result
    
    async def update(
        self,
        entry_id: int,
        content: Optional[str] = None,
        importance: Optional[int] = None,
    ) -> Optional[MemoryEntry]:
        """Обновить запись в памяти."""
        async with get_session_context() as session:
            result = await session.execute(
                select(MemoryEntry).where(MemoryEntry.id == entry_id)
            )
            entry = result.scalar_one_or_none()
            
            if not entry:
                return None
            
            if content is not None:
                entry.content = content
            if importance is not None:
                entry.importance = importance
            
            entry.updated_at = datetime.now()
            await session.commit()
            await session.refresh(entry)
            
            return entry
    
    async def delete(self, entry_id: int) -> bool:
        """Удалить запись."""
        async with get_session_context() as session:
            result = await session.execute(
                select(MemoryEntry).where(MemoryEntry.id == entry_id)
            )
            entry = result.scalar_one_or_none()
            
            if entry:
                await session.delete(entry)
                await session.commit()
                return True
            
            return False
    
    async def delete_expired(self) -> int:
        """Удалить истёкшие записи. Возвращает количество удалённых."""
        async with get_session_context() as session:
            result = await session.execute(
                MemoryEntry.__table__.delete().where(
                    and_(
                        MemoryEntry.expires_at.isnot(None),
                        MemoryEntry.expires_at < datetime.now()
                    )
                )
            )
            await session.commit()
            return result.rowcount
    
    async def count_by_user(self, user_id: int) -> int:
        """Количество записей у пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(MemoryEntry.id)).where(
                    MemoryEntry.user_id == user_id
                )
            )
            return result.scalar() or 0
    
    async def search(
        self,
        user_id: int,
        query: str,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Поиск по содержимому памяти."""
        async with get_session_context() as session:
            result = await session.execute(
                select(MemoryEntry).where(
                    and_(
                        MemoryEntry.user_id == user_id,
                        MemoryEntry.content.ilike(f"%{query}%")
                    )
                ).order_by(MemoryEntry.importance.desc()).limit(limit)
            )
            return list(result.scalars().all())
    
    async def upsert_by_category(
        self,
        user_id: int,
        category: str,
        content: str,
        importance: int = 5,
    ) -> MemoryEntry:
        """
        Создать или обновить запись в категории.
        Если в категории уже есть запись с похожим содержимым — обновляет.
        """
        async with get_session_context() as session:
            # Ищем существующую запись в категории
            existing = await session.execute(
                select(MemoryEntry).where(
                    and_(
                        MemoryEntry.user_id == user_id,
                        MemoryEntry.category == category
                    )
                ).order_by(MemoryEntry.updated_at.desc()).limit(1)
            )
            entry = existing.scalar_one_or_none()
            
            if entry:
                # Обновляем существующую
                entry.content = content
                entry.importance = max(entry.importance, importance)
                entry.updated_at = datetime.now()
                await session.commit()
                await session.refresh(entry)
                return entry
            else:
                # Создаём новую
                entry = MemoryEntry(
                    user_id=user_id,
                    category=category,
                    content=content,
                    importance=importance,
                )
                session.add(entry)
                await session.commit()
                await session.refresh(entry)
                return entry

    async def get_recent_topics(
        self,
        user_id: int,
        limit: int = 5,
    ) -> List[str]:
        """
        Получить недавние темы из памяти.
        Возвращает список категорий/тем.
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(MemoryEntry.category)
                .where(MemoryEntry.user_id == user_id)
                .order_by(MemoryEntry.updated_at.desc())
                .distinct()
                .limit(limit)
            )
            return [row[0] for row in result.all()]
