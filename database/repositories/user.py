"""
User repository.
CRUD операции для пользователей.
"""

from datetime import datetime
from typing import Optional, List, Tuple, Any, Dict
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import User, Subscription, Message


class UserRepository:
    """Репозиторий для работы с пользователями."""
    
    async def get(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
    
    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> Tuple[User, bool]:
        """
        Получить или создать пользователя.
        Возвращает (user, created).
        """
        async with get_session_context() as session:
            # Пробуем найти
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Обновляем username/first_name если изменились
                if username and user.username != username:
                    user.username = username
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                await session.commit()
                return user, False
            
            # Создаём нового
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            # Создаём бесплатную подписку
            subscription = Subscription(
                user_id=user.id,
                plan="free",
                status="active",
            )
            session.add(subscription)
            await session.commit()
            
            return user, True
    
    async def update(self, user_id: int, **kwargs) -> Optional[User]:
        """Обновить данные пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            user.updated_at = datetime.now()
            await session.commit()
            await session.refresh(user)
            
            return user
    
    async def update_last_active(self, user_id: int) -> None:
        """Обновить время последней активности."""
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.last_active_at = datetime.now()
                await session.commit()
    
    async def get_paginated(
        self,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[User], int]:
        """
        Получить пагинированный список пользователей.
        Возвращает (users, total_count).
        """
        async with get_session_context() as session:
            query = select(User)
            count_query = select(func.count(User.id))
            
            # Поиск
            if search:
                search_filter = or_(
                    User.display_name.ilike(f"%{search}%"),
                    User.username.ilike(f"%{search}%"),
                    User.first_name.ilike(f"%{search}%"),
                    User.telegram_id.cast(String).ilike(f"%{search}%"),
                )
                query = query.where(search_filter)
                count_query = count_query.where(search_filter)
            
            # Фильтры
            if filters:
                if "subscription_plan" in filters:
                    query = query.join(Subscription).where(
                        Subscription.plan == filters["subscription_plan"]
                    )
                    count_query = count_query.join(Subscription).where(
                        Subscription.plan == filters["subscription_plan"]
                    )
            
            # Сортировка
            sort_column = getattr(User, sort_by, User.created_at)
            if sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Пагинация
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page)
            
            # Выполняем запросы
            result = await session.execute(query)
            users = result.scalars().all()
            
            count_result = await session.execute(count_query)
            total = count_result.scalar()
            
            return list(users), total
    
    async def get_active_count(self, since: datetime) -> int:
        """Количество активных пользователей с определённой даты."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(User.id)).where(
                    User.last_active_at >= since
                )
            )
            return result.scalar() or 0
    
    async def get_new_count(self, since: datetime) -> int:
        """Количество новых пользователей с определённой даты."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(User.id)).where(
                    User.created_at >= since
                )
            )
            return result.scalar() or 0
    
    async def get_days_active(self, user_id: int) -> int:
        """Количество дней активности пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(func.distinct(func.date(Message.created_at)))).where(
                    Message.user_id == user_id
                )
            )
            return result.scalar() or 0

    async def block_user(
        self,
        telegram_id: int,
        reason: Optional[str] = None,
    ) -> Optional[User]:
        """
        Заблокировать пользователя.

        Args:
            telegram_id: Telegram ID пользователя
            reason: Причина блокировки

        Returns:
            Обновлённый пользователь или None если не найден
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            user.is_blocked = True
            user.block_reason = reason
            user.updated_at = datetime.now()

            await session.commit()
            await session.refresh(user)

            return user

    async def unblock_user(self, telegram_id: int) -> Optional[User]:
        """
        Разблокировать пользователя.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            Обновлённый пользователь или None если не найден
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            user.is_blocked = False
            user.block_reason = None
            user.updated_at = datetime.now()

            await session.commit()
            await session.refresh(user)

            return user

    async def get_blocked_users(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[User], int]:
        """
        Получить список заблокированных пользователей.

        Returns:
            (users, total_count)
        """
        async with get_session_context() as session:
            query = (
                select(User)
                .where(User.is_blocked == True)
                .order_by(User.updated_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )

            count_query = select(func.count(User.id)).where(User.is_blocked == True)

            result = await session.execute(query)
            users = result.scalars().all()

            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0

            return list(users), total
