"""
API роуты для воронки продаж.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from sqlalchemy import func, and_

from webapp.api.middleware import get_current_admin
from database.session import get_session_context
from database.models import User, Payment
from services.google_analytics import analytics_service


router = APIRouter()


class FunnelStats(BaseModel):
    """Статистика воронки продаж."""
    visitors: int = Field(..., description="Посетители лендинга")
    clicks: int = Field(..., description="Клики на кнопку бота")
    started: int = Field(..., description="Запустили бота")
    onboarded: int = Field(..., description="Завершили онбординг")
    premium: int = Field(..., description="Оплатили Premium")
    avg_check: float = Field(..., description="Средний чек (руб)")
    total_revenue: float = Field(..., description="Общая выручка (руб)")


@router.get("/funnel", response_model=FunnelStats)
async def get_funnel_stats(
    days: int = 7,
    admin_data: dict = Depends(get_current_admin)
):
    """
    Получить статистику воронки продаж за последние N дней.

    Этапы воронки:
    1. Посетители лендинга (из GA)
    2. Клики на кнопку бота (событие bot_start_click из GA)
    3. Запустили бота (пользователи в БД)
    4. Завершили онбординг (users.onboarding_completed=True)
    5. Оплатили Premium (есть успешный платеж)

    Args:
        days: Количество дней для анализа (по умолчанию 7)
        admin_data: Данные администратора (из middleware)

    Returns:
        FunnelStats с метриками воронки
    """
    try:
        # Дата начала периода
        start_date = datetime.now() - timedelta(days=days)

        # Этап 1: Посетители лендинга (из Google Analytics)
        ga_stats = analytics_service.get_landing_stats(days=days)
        visitors = ga_stats["unique_users"]
        clicks = ga_stats["conversions"]  # bot_start_click events

        # Этап 2-5: Данные из базы
        with get_session_context() as session:
            # Этап 3: Запустили бота (все пользователи за период)
            started = session.query(func.count(User.telegram_id)).filter(
                User.created_at >= start_date
            ).scalar() or 0

            # Этап 4: Завершили онбординг
            onboarded = session.query(func.count(User.telegram_id)).filter(
                and_(
                    User.created_at >= start_date,
                    User.onboarding_completed == True
                )
            ).scalar() or 0

            # Этап 5: Оплатили Premium (успешные платежи)
            premium_users = session.query(
                func.count(func.distinct(Payment.user_telegram_id))
            ).filter(
                and_(
                    Payment.created_at >= start_date,
                    Payment.status == "succeeded"
                )
            ).scalar() or 0

            # Средний чек и общая выручка
            revenue_stats = session.query(
                func.avg(Payment.amount),
                func.sum(Payment.amount)
            ).filter(
                and_(
                    Payment.created_at >= start_date,
                    Payment.status == "succeeded"
                )
            ).first()

            avg_check = float(revenue_stats[0] or 0)
            total_revenue = float(revenue_stats[1] or 0)

        return FunnelStats(
            visitors=visitors,
            clicks=clicks,
            started=started,
            onboarded=onboarded,
            premium=premium_users,
            avg_check=avg_check,
            total_revenue=total_revenue,
        )

    except Exception as e:
        # При ошибке возвращаем нулевые значения
        return FunnelStats(
            visitors=0,
            clicks=0,
            started=0,
            onboarded=0,
            premium=0,
            avg_check=0,
            total_revenue=0,
        )
