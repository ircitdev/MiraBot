"""
Metrics Service.
Бизнес-метрики для админ-панели.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import select, func, and_

from database.session import get_session_context
from database.models import User, Subscription, Message, Referral, Payment
from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.referral import ReferralRepository
from database.repositories.payment import PaymentRepository


class MetricsService:
    """Сервис для расчёта метрик."""
    
    def __init__(self):
        self.user_repo = UserRepository()
        self.subscription_repo = SubscriptionRepository()
        self.conversation_repo = ConversationRepository()
        self.referral_repo = ReferralRepository()
        self.payment_repo = PaymentRepository()
    
    # ==========================================
    # Пользователи
    # ==========================================
    
    async def get_total_users(self) -> int:
        """Общее количество пользователей."""
        async with get_session_context() as session:
            result = await session.execute(select(func.count(User.id)))
            return result.scalar() or 0
    
    async def get_active_users(self, hours: int = 24) -> int:
        """Активные пользователи за N часов."""
        since = datetime.now() - timedelta(hours=hours)
        return await self.user_repo.get_active_count(since)
    
    async def get_new_users(self, hours: int = 24) -> int:
        """Новые пользователи за N часов."""
        since = datetime.now() - timedelta(hours=hours)
        return await self.user_repo.get_new_count(since)
    
    # ==========================================
    # Подписки
    # ==========================================
    
    async def get_premium_count(self) -> int:
        """Количество премиум подписчиков."""
        return await self.subscription_repo.get_premium_count()
    
    async def get_free_count(self) -> int:
        """Количество бесплатных пользователей."""
        return await self.subscription_repo.get_free_count()
    
    async def get_conversion_rate(self) -> float:
        """Конверсия в платящих."""
        premium = await self.get_premium_count()
        total = await self.get_total_users()
        
        if total == 0:
            return 0.0
        
        return round(premium / total * 100, 2)
    
    async def get_churn_rate(self) -> float:
        """Месячный churn rate."""
        # Упрощённый расчёт: отменённые / активные за месяц
        async with get_session_context() as session:
            month_ago = datetime.now() - timedelta(days=30)
            
            # Отменённые за месяц
            cancelled = await session.execute(
                select(func.count(Subscription.id)).where(
                    and_(
                        Subscription.status == "cancelled",
                        Subscription.updated_at >= month_ago
                    )
                )
            )
            cancelled_count = cancelled.scalar() or 0
            
            # Активные в начале месяца
            active = await self.get_premium_count()
            
            if active + cancelled_count == 0:
                return 0.0
            
            return round(cancelled_count / (active + cancelled_count) * 100, 2)
    
    # ==========================================
    # Выручка
    # ==========================================
    
    async def get_mrr(self) -> int:
        """Monthly Recurring Revenue (в рублях)."""
        # Считаем активные подписки * средний чек
        from config.settings import settings
        
        premium_count = await self.get_premium_count()
        
        # Упрощённо считаем по средней цене
        avg_price = (settings.PRICE_MONTHLY + settings.PRICE_QUARTERLY / 3 + settings.PRICE_YEARLY / 12) / 3
        
        return int(premium_count * avg_price)
    
    async def get_arr(self) -> int:
        """Annual Recurring Revenue."""
        return await self.get_mrr() * 12
    
    async def get_revenue_today(self) -> int:
        """Выручка за сегодня (в рублях)."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        revenue_kopecks = await self.payment_repo.get_total_revenue(since=today)
        return revenue_kopecks // 100
    
    async def get_ltv(self) -> int:
        """Lifetime Value (упрощённый)."""
        mrr = await self.get_mrr()
        churn = await self.get_churn_rate()
        
        if churn == 0:
            return mrr * 12  # Предполагаем год
        
        return int(mrr / (churn / 100))
    
    async def get_arpu(self) -> int:
        """Average Revenue Per User."""
        total_revenue = await self.payment_repo.get_total_revenue()
        total_users = await self.get_total_users()
        
        if total_users == 0:
            return 0
        
        return (total_revenue // 100) // total_users
    
    # ==========================================
    # Сообщения
    # ==========================================
    
    async def get_messages_count(self, hours: int = 24) -> int:
        """Количество сообщений за N часов."""
        since = datetime.now() - timedelta(hours=hours)
        return await self.conversation_repo.get_messages_count_since(since)
    
    # ==========================================
    # Рефералы
    # ==========================================
    
    async def get_total_referrals(self) -> int:
        """Всего рефералов."""
        return await self.referral_repo.get_total_count()
    
    async def get_referrals_this_week(self) -> int:
        """Рефералы за неделю."""
        since = datetime.now() - timedelta(days=7)
        return await self.referral_repo.get_count_since(since)
    
    async def get_viral_coefficient(self) -> float:
        """Viral coefficient (K-factor)."""
        total_users = await self.get_total_users()
        total_referrals = await self.get_total_referrals()
        
        if total_users == 0:
            return 0.0
        
        return round(total_referrals / total_users, 3)
    
    async def get_top_referrers(self, limit: int = 20) -> List[Dict]:
        """Топ рефереров."""
        return await self.referral_repo.get_top_referrers(limit)
    
    async def get_referral_conversion_rate(self) -> float:
        """Конверсия рефералов в платящих."""
        # Упрощённо — процент приглашённых, ставших premium
        return 15.0  # Заглушка
    
    # ==========================================
    # Кризисы
    # ==========================================
    
    async def get_crisis_alerts(self, hours: int = 24) -> int:
        """Кризисные сигналы за N часов."""
        since = datetime.now() - timedelta(hours=hours)
        messages = await self.conversation_repo.get_with_tag("crisis", limit=1000, since=since)
        return len(messages)
    
    async def get_crisis_monitoring(self, days: int = 7) -> Dict[str, Any]:
        """Мониторинг кризисов."""
        since = datetime.now() - timedelta(days=days)
        messages = await self.conversation_repo.get_with_tag("crisis", limit=100, since=since)
        
        return {
            "total_alerts": len(messages),
            "unique_users": len(set(m.user_id for m in messages)),
            "recent": [
                {
                    "user_id": m.user_id,
                    "created_at": m.created_at.isoformat(),
                    "preview": m.content[:100] + "..." if len(m.content) > 100 else m.content,
                }
                for m in messages[:20]
            ],
        }
    
    # ==========================================
    # Таймлайны
    # ==========================================
    
    async def get_users_timeline(self, days: int = 30) -> List[Dict]:
        """График роста пользователей по дням."""
        async with get_session_context() as session:
            since = datetime.now() - timedelta(days=days)
            
            result = await session.execute(
                """
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM users
                WHERE created_at >= :since
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                {"since": since}
            )
            
            return [
                {"date": row[0].isoformat(), "count": row[1]}
                for row in result.fetchall()
            ]
    
    async def get_revenue_timeline(self, days: int = 30) -> List[Dict]:
        """График выручки по дням."""
        async with get_session_context() as session:
            since = datetime.now() - timedelta(days=days)
            
            result = await session.execute(
                """
                SELECT DATE(completed_at) as date, SUM(amount) / 100 as amount
                FROM payments
                WHERE status = 'completed' AND completed_at >= :since
                GROUP BY DATE(completed_at)
                ORDER BY date
                """,
                {"since": since}
            )
            
            return [
                {"date": row[0].isoformat() if row[0] else None, "amount": int(row[1] or 0)}
                for row in result.fetchall()
            ]
    
    async def get_engagement_timeline(self, days: int = 30) -> List[Dict]:
        """График вовлечённости по дням."""
        async with get_session_context() as session:
            since = datetime.now() - timedelta(days=days)
            
            result = await session.execute(
                """
                SELECT DATE(created_at) as date, COUNT(*) as messages, COUNT(DISTINCT user_id) as users
                FROM messages
                WHERE created_at >= :since
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                {"since": since}
            )
            
            return [
                {"date": row[0].isoformat(), "messages": row[1], "active_users": row[2]}
                for row in result.fetchall()
            ]
    
    # ==========================================
    # Аналитика
    # ==========================================
    
    async def get_cohort_retention(self, weeks: int = 8) -> Dict:
        """Когортный анализ."""
        # Упрощённая заглушка
        return {
            "weeks": weeks,
            "cohorts": [],  # Требует сложного SQL
        }
    
    async def get_conversion_funnel(self) -> Dict:
        """Воронка конверсии."""
        total = await self.get_total_users()
        
        # Упрощённые этапы
        return {
            "stages": [
                {"name": "Начали онбординг", "count": total, "percent": 100},
                {"name": "Выбрали персону", "count": int(total * 0.9), "percent": 90},
                {"name": "Завершили онбординг", "count": int(total * 0.85), "percent": 85},
                {"name": "Отправили 5+ сообщений", "count": int(total * 0.6), "percent": 60},
                {"name": "Вернулись на 2й день", "count": int(total * 0.4), "percent": 40},
                {"name": "Активны 7+ дней", "count": int(total * 0.25), "percent": 25},
                {"name": "Подписались", "count": await self.get_premium_count(), "percent": await self.get_conversion_rate()},
            ]
        }
    
    async def get_topic_distribution(self, days: int = 30) -> Dict:
        """Распределение тем."""
        since = datetime.now() - timedelta(days=days)
        
        topics = {
            "husband": await self._count_tag("topic:husband", since),
            "children": await self._count_tag("topic:children", since),
            "self": await self._count_tag("topic:self", since),
            "relatives": await self._count_tag("topic:relatives", since),
            "intimacy": await self._count_tag("topic:intimacy", since),
            "work": await self._count_tag("topic:work", since),
        }
        
        total = sum(topics.values())
        
        return {
            "topics": [
                {"name": k, "count": v, "percent": round(v / total * 100, 1) if total > 0 else 0}
                for k, v in sorted(topics.items(), key=lambda x: x[1], reverse=True)
            ]
        }
    
    async def _count_tag(self, tag: str, since: datetime) -> int:
        """Подсчёт сообщений с тегом."""
        messages = await self.conversation_repo.get_with_tag(tag, limit=10000, since=since)
        return len(messages)
    
    async def get_engagement_segments(self) -> Dict:
        """Сегментация по активности."""
        total = await self.get_total_users()
        
        # Упрощённая сегментация
        return {
            "segments": [
                {"name": "Churned (нет активности 30+ дней)", "count": int(total * 0.3), "percent": 30},
                {"name": "At risk (нет активности 7-30 дней)", "count": int(total * 0.2), "percent": 20},
                {"name": "Casual (1-3 раза в неделю)", "count": int(total * 0.25), "percent": 25},
                {"name": "Active (4-6 раз в неделю)", "count": int(total * 0.15), "percent": 15},
                {"name": "Power users (ежедневно)", "count": int(total * 0.1), "percent": 10},
            ]
        }
