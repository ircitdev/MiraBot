"""
AdminUser repository.
CRUD операции для администраторов и модераторов.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import AdminUser


class AdminUserRepository:
    """Репозиторий для работы с администраторами и модераторами."""

    async def get(self, admin_id: int) -> Optional[AdminUser]:
        """Получить админа по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[AdminUser]:
        """Получить админа по Telegram ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        role: str = 'moderator',
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        created_by_id: Optional[int] = None,
        avatar_url: Optional[str] = None,
        accent_color: str = '#1976d2',
    ) -> AdminUser:
        """
        Создать нового администратора/модератора.

        Args:
            telegram_id: Telegram ID пользователя
            role: Роль ('admin' или 'moderator')
            username: Username в Telegram
            first_name: Имя
            last_name: Фамилия
            created_by_id: ID создателя (другого админа)
            avatar_url: URL аватара
            accent_color: Цвет интерфейса (HEX)

        Returns:
            Созданный AdminUser
        """
        async with get_session_context() as session:
            admin_user = AdminUser(
                telegram_id=telegram_id,
                role=role,
                username=username,
                first_name=first_name,
                last_name=last_name,
                created_by_id=created_by_id,
                avatar_url=avatar_url,
                accent_color=accent_color,
                is_active=True,
            )

            session.add(admin_user)
            await session.commit()
            await session.refresh(admin_user)

            return admin_user

    async def update(
        self,
        admin_id: int,
        **kwargs
    ) -> Optional[AdminUser]:
        """
        Обновить данные администратора.

        Args:
            admin_id: ID администратора
            **kwargs: Поля для обновления

        Returns:
            Обновлённый AdminUser или None
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin_user = result.scalar_one_or_none()

            if not admin_user:
                return None

            # Обновляем только переданные поля
            for key, value in kwargs.items():
                if hasattr(admin_user, key):
                    setattr(admin_user, key, value)

            await session.commit()
            await session.refresh(admin_user)

            return admin_user

    async def update_last_login(self, admin_id: int) -> None:
        """Обновить время последнего входа."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin_user = result.scalar_one_or_none()

            if admin_user:
                admin_user.last_login_at = datetime.now()
                await session.commit()

    async def deactivate(self, admin_id: int) -> bool:
        """
        Деактивировать администратора (мягкое удаление).

        Returns:
            True если деактивирован, False если не найден
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin_user = result.scalar_one_or_none()

            if not admin_user:
                return False

            admin_user.is_active = False
            await session.commit()

            return True

    async def activate(self, admin_id: int) -> bool:
        """
        Активировать администратора.

        Returns:
            True если активирован, False если не найден
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin_user = result.scalar_one_or_none()

            if not admin_user:
                return False

            admin_user.is_active = True
            await session.commit()

            return True

    async def list_all(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[AdminUser]:
        """
        Получить список всех администраторов.

        Args:
            role: Фильтр по роли ('admin', 'moderator')
            is_active: Фильтр по активности

        Returns:
            Список AdminUser
        """
        async with get_session_context() as session:
            query = select(AdminUser)

            if role is not None:
                query = query.where(AdminUser.role == role)

            if is_active is not None:
                query = query.where(AdminUser.is_active == is_active)

            query = query.order_by(AdminUser.created_at.desc())

            result = await session.execute(query)
            return list(result.scalars().all())

    async def check_permission(
        self,
        telegram_id: int,
        required_role: str = 'moderator'
    ) -> bool:
        """
        Проверить права доступа пользователя.

        Args:
            telegram_id: Telegram ID пользователя
            required_role: Требуемая роль ('admin' или 'moderator')

        Returns:
            True если есть права, False если нет
        """
        admin_user = await self.get_by_telegram_id(telegram_id)

        if not admin_user or not admin_user.is_active:
            return False

        # Админ имеет все права
        if admin_user.role == 'admin':
            return True

        # Модератор имеет права только если требуется роль модератора
        if required_role == 'moderator' and admin_user.role == 'moderator':
            return True

        return False
