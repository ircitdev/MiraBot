"""
Analytics router.
Аналитика и отчёты.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta

from admin.auth import get_current_admin
from admin.services.metrics import MetricsService


router = APIRouter()
metrics = MetricsService()


@router.get("/cohorts")
async def get_cohort_retention(
    weeks: int = Query(8, ge=1, le=52),
    admin = Depends(get_current_admin),
):
    """Когортный анализ удержания."""
    
    return await metrics.get_cohort_retention(weeks=weeks)


@router.get("/funnel")
async def get_conversion_funnel(admin = Depends(get_current_admin)):
    """Воронка конверсии."""
    
    return await metrics.get_conversion_funnel()


@router.get("/topics")
async def get_topic_distribution(
    days: int = Query(30, ge=1, le=365),
    admin = Depends(get_current_admin),
):
    """Распределение тем в разговорах."""
    
    return await metrics.get_topic_distribution(days=days)


@router.get("/engagement-segments")
async def get_engagement_segments(admin = Depends(get_current_admin)):
    """Сегментация пользователей по активности."""
    
    return await metrics.get_engagement_segments()


@router.get("/revenue")
async def get_revenue_analytics(
    days: int = Query(30, ge=1, le=365),
    admin = Depends(get_current_admin),
):
    """Аналитика выручки."""
    
    return {
        "mrr": await metrics.get_mrr(),
        "arr": await metrics.get_arr(),
        "churn_rate": await metrics.get_churn_rate(),
        "ltv": await metrics.get_ltv(),
        "arpu": await metrics.get_arpu(),
        "timeline": await metrics.get_revenue_timeline(days=days),
    }


@router.get("/referrals")
async def get_referral_analytics(admin = Depends(get_current_admin)):
    """Аналитика реферальной программы."""
    
    return {
        "viral_coefficient": await metrics.get_viral_coefficient(),
        "total_referrals": await metrics.get_total_referrals(),
        "top_referrers": await metrics.get_top_referrers(limit=20),
        "conversion_rate": await metrics.get_referral_conversion_rate(),
    }


@router.get("/crisis-monitoring")
async def get_crisis_monitoring(
    days: int = Query(7, ge=1, le=30),
    admin = Depends(get_current_admin),
):
    """Мониторинг кризисных ситуаций."""
    
    return await metrics.get_crisis_monitoring(days=days)
