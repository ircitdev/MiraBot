"""
Payment repository.
CRUD операции для платежей.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import Payment


class PaymentRepository:
    """Репозиторий для работы с платежами."""
    
    async def create(
        self,
        user_id: int,
        amount: int,
        plan: str,
        description: str,
        yookassa_payment_id: Optional[str] = None,
        yookassa_status: Optional[str] = None,
        is_recurring: bool = False,
    ) -> Payment:
        """Создать запись о платеже."""
        async with get_session_context() as session:
            payment = Payment(
                user_id=user_id,
                amount=amount,
                plan=plan,
                description=description,
                yookassa_payment_id=yookassa_payment_id,
                yookassa_status=yookassa_status,
                is_recurring=is_recurring,
                status="pending",
            )
            session.add(payment)
            await session.commit()
            await session.refresh(payment)
            
            return payment
    
    async def get(self, payment_id: int) -> Optional[Payment]:
        """Получить платёж по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Payment).where(Payment.id == payment_id)
            )
            return result.scalar_one_or_none()
    
    async def get_by_yookassa_id(self, yookassa_id: str) -> Optional[Payment]:
        """Получить платёж по ID ЮKassa."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Payment).where(Payment.yookassa_payment_id == yookassa_id)
            )
            return result.scalar_one_or_none()
    
    async def update(self, payment_id: int, **kwargs) -> Optional[Payment]:
        """Обновить платёж."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Payment).where(Payment.id == payment_id)
            )
            payment = result.scalar_one_or_none()
            
            if not payment:
                return None
            
            for key, value in kwargs.items():
                if hasattr(payment, key):
                    setattr(payment, key, value)
            
            if kwargs.get("status") == "completed" and not payment.completed_at:
                payment.completed_at = datetime.now()
            
            await session.commit()
            await session.refresh(payment)
            
            return payment
    
    async def get_by_user(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Payment]:
        """Получить платежи пользователя."""
        async with get_session_context() as session:
            query = select(Payment).where(Payment.user_id == user_id)
            
            if status:
                query = query.where(Payment.status == status)
            
            query = query.order_by(Payment.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_recent_for_subscription(
        self,
        subscription_id: int,
        hours: int = 24,
    ) -> Optional[Payment]:
        """Получить недавний платёж для подписки."""
        async with get_session_context() as session:
            since = datetime.now() - timedelta(hours=hours)
            
            result = await session.execute(
                select(Payment).where(
                    and_(
                        Payment.subscription_id == subscription_id,
                        Payment.created_at >= since
                    )
                ).order_by(Payment.created_at.desc()).limit(1)
            )
            return result.scalar_one_or_none()
    
    async def get_total_revenue(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> int:
        """Общая выручка за период (в копейках)."""
        async with get_session_context() as session:
            query = select(func.sum(Payment.amount)).where(
                Payment.status == "completed"
            )
            
            if since:
                query = query.where(Payment.completed_at >= since)
            if until:
                query = query.where(Payment.completed_at < until)
            
            result = await session.execute(query)
            return result.scalar() or 0
    
    async def get_payments_count(
        self,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Количество платежей."""
        async with get_session_context() as session:
            query = select(func.count(Payment.id))
            
            if status:
                query = query.where(Payment.status == status)
            if since:
                query = query.where(Payment.created_at >= since)
            
            result = await session.execute(query)
            return result.scalar() or 0
    
    async def get_revenue_by_plan(
        self,
        since: Optional[datetime] = None,
    ) -> dict:
        """Выручка по планам подписки."""
        async with get_session_context() as session:
            query = """
                SELECT 
                    plan,
                    SUM(amount) as total,
                    COUNT(*) as count
                FROM payments
                WHERE status = 'completed'
            """
            
            params = {}
            if since:
                query += " AND completed_at >= :since"
                params["since"] = since
            
            query += " GROUP BY plan"
            
            result = await session.execute(query, params)
            
            return {
                row[0]: {"total": row[1], "count": row[2]}
                for row in result.fetchall()
            }
    
    async def get_refunds_count(self, since: Optional[datetime] = None) -> int:
        """Количество возвратов."""
        async with get_session_context() as session:
            query = select(func.count(Payment.id)).where(
                Payment.status == "refunded"
            )
            
            if since:
                query = query.where(Payment.created_at >= since)
            
            result = await session.execute(query)
            return result.scalar() or 0
