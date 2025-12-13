"""
Subscription repository.
CRUD операции для подписок.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import Subscription


class SubscriptionRepository:
    """Репозиторий для работы с подписками."""
    
    async def get(self, subscription_id: int) -> Optional[Subscription]:
        """Получить подписку по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            return result.scalar_one_or_none()
    
    async def get_active(self, user_id: int) -> Optional[Subscription]:
        """Получить активную подписку пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user_id,
                        Subscription.status == "active"
                    )
                )
            )
            return result.scalar_one_or_none()
    
    async def create(
        self,
        user_id: int,
        plan: str,
        duration_days: int,
        payment_id: Optional[int] = None,
    ) -> Subscription:
        """Создать новую подписку."""
        async with get_session_context() as session:
            # Деактивируем старую подписку если есть
            old_sub = await session.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user_id,
                        Subscription.status == "active"
                    )
                )
            )
            old = old_sub.scalar_one_or_none()
            if old:
                old.status = "expired"
            
            # Создаём новую
            subscription = Subscription(
                user_id=user_id,
                plan=plan,
                status="active",
                expires_at=datetime.now() + timedelta(days=duration_days),
            )
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)
            
            return subscription
    
    async def create_trial(self, user_id: int, days: int) -> Subscription:
        """Создать пробную подписку."""
        return await self.create(
            user_id=user_id,
            plan="trial",
            duration_days=days,
        )
    
    async def update(self, subscription_id: int, **kwargs) -> Optional[Subscription]:
        """Обновить подписку."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return None
            
            for key, value in kwargs.items():
                if hasattr(subscription, key):
                    setattr(subscription, key, value)
            
            subscription.updated_at = datetime.now()
            await session.commit()
            await session.refresh(subscription)
            
            return subscription
    
    async def extend(self, subscription_id: int, new_expires_at: datetime) -> Optional[Subscription]:
        """Продлить подписку до указанной даты."""
        return await self.update(subscription_id, expires_at=new_expires_at)
    
    async def extend_days(self, subscription_id: int, days: int) -> Optional[Subscription]:
        """Продлить подписку на указанное количество дней."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return None
            
            if subscription.expires_at:
                new_expires = subscription.expires_at + timedelta(days=days)
            else:
                new_expires = datetime.now() + timedelta(days=days)
            
            subscription.expires_at = new_expires
            subscription.plan = "premium"  # Апгрейд до премиума
            subscription.updated_at = datetime.now()
            
            await session.commit()
            await session.refresh(subscription)
            
            return subscription
    
    async def cancel(self, subscription_id: int) -> Optional[Subscription]:
        """Отменить подписку."""
        return await self.update(
            subscription_id,
            status="cancelled",
            auto_renew=False,
        )
    
    async def increment_messages(self, subscription_id: int) -> None:
        """Увеличить счётчик сообщений."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            subscription = result.scalar_one_or_none()
            
            if subscription:
                # Сбрасываем счётчик если новый день
                today = datetime.now().date()
                if subscription.messages_reset_at != today:
                    subscription.messages_today = 0
                    subscription.messages_reset_at = today
                
                subscription.messages_today += 1
                await session.commit()
    
    async def reset_daily_messages(self, subscription_id: int) -> None:
        """Сбросить дневной счётчик сообщений."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.id == subscription_id)
            )
            subscription = result.scalar_one_or_none()
            
            if subscription:
                subscription.messages_today = 0
                subscription.messages_reset_at = datetime.now().date()
                await session.commit()
    
    async def get_expiring(self, days: int, exact: bool = False) -> List[Subscription]:
        """
        Получить подписки, истекающие в ближайшие N дней.
        Если exact=True, только подписки истекающие ровно через N дней.
        """
        async with get_session_context() as session:
            now = datetime.now()
            
            if exact:
                target_date = now + timedelta(days=days)
                query = select(Subscription).where(
                    and_(
                        Subscription.status == "active",
                        func.date(Subscription.expires_at) == target_date.date()
                    )
                )
            else:
                query = select(Subscription).where(
                    and_(
                        Subscription.status == "active",
                        Subscription.expires_at <= now + timedelta(days=days),
                        Subscription.expires_at > now
                    )
                )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_premium_count(self) -> int:
        """Количество активных премиум подписок."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Subscription.id)).where(
                    and_(
                        Subscription.plan == "premium",
                        Subscription.status == "active"
                    )
                )
            )
            return result.scalar() or 0
    
    async def get_free_count(self) -> int:
        """Количество бесплатных подписок."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.plan == "free"
                )
            )
            return result.scalar() or 0
