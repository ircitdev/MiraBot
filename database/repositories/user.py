"""
User repository.
CRUD операции для пользователей.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Any, Dict, AsyncGenerator
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
            
            # Создаём trial подписку на 3 дня
            subscription = Subscription(
                user_id=user.id,
                plan="trial",
                status="active",
                expires_at=datetime.now() + timedelta(days=3),
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

    async def get_all_telegram_ids(
        self,
        segment: str = "all",
        exclude_blocked: bool = True,
    ) -> List[int]:
        """
        Получить список telegram_id для рассылки.

        Args:
            segment: Сегмент пользователей:
                - "all" — все пользователи
                - "premium" — только с premium подпиской
                - "free" — только с free подпиской
                - "active_week" — активные за последнюю неделю
                - "active_month" — активные за последний месяц
                - "inactive" — неактивные более месяца
            exclude_blocked: Исключить заблокированных

        Returns:
            Список telegram_id
        """
        async with get_session_context() as session:
            query = select(User.telegram_id)

            # Исключаем заблокированных
            if exclude_blocked:
                query = query.where(User.is_blocked == False)

            # Фильтры по сегментам
            if segment == "premium":
                query = query.join(Subscription).where(
                    and_(
                        Subscription.plan == "premium",
                        Subscription.status == "active",
                    )
                )
            elif segment == "free":
                query = query.join(Subscription).where(
                    Subscription.plan == "free"
                )
            elif segment == "active_week":
                week_ago = datetime.now() - timedelta(days=7)
                query = query.where(User.last_active_at >= week_ago)
            elif segment == "active_month":
                month_ago = datetime.now() - timedelta(days=30)
                query = query.where(User.last_active_at >= month_ago)
            elif segment == "inactive":
                month_ago = datetime.now() - timedelta(days=30)
                query = query.where(
                    or_(
                        User.last_active_at < month_ago,
                        User.last_active_at.is_(None),
                    )
                )

            result = await session.execute(query)
            return [row[0] for row in result.fetchall()]

    async def count_by_segment(self, segment: str = "all") -> int:
        """
        Подсчитать количество пользователей в сегменте.

        Args:
            segment: Сегмент (см. get_all_telegram_ids)

        Returns:
            Количество пользователей
        """
        async with get_session_context() as session:
            query = select(func.count(User.id)).where(User.is_blocked == False)

            if segment == "premium":
                query = (
                    select(func.count(User.id))
                    .select_from(User)
                    .join(Subscription)
                    .where(
                        and_(
                            User.is_blocked == False,
                            Subscription.plan == "premium",
                            Subscription.status == "active",
                        )
                    )
                )
            elif segment == "free":
                query = (
                    select(func.count(User.id))
                    .select_from(User)
                    .join(Subscription)
                    .where(
                        and_(
                            User.is_blocked == False,
                            Subscription.plan == "free",
                        )
                    )
                )
            elif segment == "active_week":
                week_ago = datetime.now() - timedelta(days=7)
                query = query.where(User.last_active_at >= week_ago)
            elif segment == "active_month":
                month_ago = datetime.now() - timedelta(days=30)
                query = query.where(User.last_active_at >= month_ago)
            elif segment == "inactive":
                month_ago = datetime.now() - timedelta(days=30)
                query = select(func.count(User.id)).where(
                    and_(
                        User.is_blocked == False,
                        or_(
                            User.last_active_at < month_ago,
                            User.last_active_at.is_(None),
                        ),
                    )
                )

            result = await session.execute(query)
            return result.scalar() or 0
    async def get_by_celebration_date(
        self,
        field: str,
        month: int,
        day: int,
    ) -> List[User]:
        """
        Получить пользователей по дате праздника (день+месяц).

        Args:
            field: Поле для проверки ('birthday' или 'anniversary')
            month: Месяц (1-12)
            day: День (1-31)

        Returns:
            Список пользователей с праздником в этот день
        """
        async with get_session_context() as session:
            from sqlalchemy import extract

            if field == 'birthday':
                query = select(User).where(
                    and_(
                        extract('month', User.birthday) == month,
                        extract('day', User.birthday) == day,
                        User.is_blocked == False,
                        User.proactive_messages == True,
                    )
                )
            elif field == 'anniversary':
                query = select(User).where(
                    and_(
                        extract('month', User.anniversary) == month,
                        extract('day', User.anniversary) == day,
                        User.is_blocked == False,
                        User.proactive_messages == True,
                    )
                )
            else:
                return []

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_communication_style(
        self,
        user_id: int,
        style: dict,
    ) -> None:
        """
        Обновить стиль общения пользователя.

        Args:
            user_id: ID пользователя
            style: Словарь со стилем общения
        """
        style["updated_at"] = datetime.now().isoformat()
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                user.communication_style = style
                user.updated_at = datetime.now()
                await session.commit()

