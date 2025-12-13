"""
Dashboard router.
Метрики и обзор.
"""

from fastapi import APIRouter, Depends
from datetime import datetime, timedelta

from admin.auth import get_current_admin
from admin.services.metrics import MetricsService


router = APIRouter()
metrics = MetricsService()


@router.get("/overview")
async def get_overview(admin = Depends(get_current_admin)):
    """Общий обзор метрик."""
    
    return {
        "users": {
            "total": await metrics.get_total_users(),
            "active_today": await metrics.get_active_users(hours=24),
            "active_week": await metrics.get_active_users(hours=24*7),
            "new_today": await metrics.get_new_users(hours=24),
            "new_week": await metrics.get_new_users(hours=24*7),
        },
        "subscriptions": {
            "premium_count": await metrics.get_premium_count(),
            "free_count": await metrics.get_free_count(),
            "conversion_rate": await metrics.get_conversion_rate(),
        },
        "revenue": {
            "mrr": await metrics.get_mrr(),
            "today": await metrics.get_revenue_today(),
        },
        "engagement": {
            "messages_today": await metrics.get_messages_count(hours=24),
            "messages_week": await metrics.get_messages_count(hours=24*7),
        },
        "referrals": {
            "total": await metrics.get_total_referrals(),
            "this_week": await metrics.get_referrals_this_week(),
        },
        "crisis": {
            "alerts_today": await metrics.get_crisis_alerts(hours=24),
        },
    }


@router.get("/charts/users")
async def get_users_chart(
    days: int = 30,
    admin = Depends(get_current_admin),
):
    """График роста пользователей."""
    
    return await metrics.get_users_timeline(days=days)


@router.get("/charts/revenue")
async def get_revenue_chart(
    days: int = 30,
    admin = Depends(get_current_admin),
):
    """График выручки."""
    
    return await metrics.get_revenue_timeline(days=days)


@router.get("/charts/engagement")
async def get_engagement_chart(
    days: int = 30,
    admin = Depends(get_current_admin),
):
    """График вовлечённости."""
    
    return await metrics.get_engagement_timeline(days=days)


@router.get("/realtime")
async def get_realtime_stats(admin = Depends(get_current_admin)):
    """Статистика за последний час."""
    
    return {
        "active_users": await metrics.get_active_users(hours=1),
        "messages": await metrics.get_messages_count(hours=1),
        "new_users": await metrics.get_new_users(hours=1),
        "crisis_alerts": await metrics.get_crisis_alerts(hours=1),
    }
