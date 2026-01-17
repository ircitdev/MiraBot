"""
API роуты для Google Analytics.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List

from webapp.api.middleware import get_current_admin
from services.google_analytics import analytics_service


router = APIRouter()


class TrafficSource(BaseModel):
    """Источник трафика."""
    source: str = Field(..., description="Название источника")
    users: int = Field(..., description="Количество пользователей")


class TimelineItem(BaseModel):
    """Элемент временной шкалы."""
    date: str = Field(..., description="Дата (YYYY-MM-DD)")
    views: int = Field(..., description="Просмотры")
    users: int = Field(..., description="Уникальные пользователи")
    conversions: int = Field(..., description="Конверсии")


class LandingStats(BaseModel):
    """Статистика лендинга."""
    views_total: int = Field(..., description="Общее количество просмотров")
    views_today: int = Field(..., description="Просмотры сегодня")
    unique_users: int = Field(..., description="Уникальные пользователи")
    users_online: int = Field(..., description="Пользователи онлайн (real-time)")
    avg_session_duration: int = Field(..., description="Средняя длительность сессии (сек)")
    bounce_rate: float = Field(..., description="Показатель отказов (%)")
    conversions: int = Field(..., description="Количество конверсий")
    top_sources: List[TrafficSource] = Field(..., description="Топ источников трафика")
    timeline: List[TimelineItem] = Field(..., description="Динамика по дням")


@router.get("/analytics/landing", response_model=LandingStats)
async def get_landing_stats(
    days: int = 7,
    admin_data: dict = Depends(get_current_admin)
):
    """
    Получить статистику лендинга за последние N дней.

    Args:
        days: Количество дней для анализа (по умолчанию 7)
        admin_data: Данные администратора (из middleware)

    Returns:
        LandingStats с метриками лендинга
    """
    try:
        # Получаем статистику за период
        stats = analytics_service.get_landing_stats(days=days)

        # Получаем real-time данные
        users_online = analytics_service.get_realtime_users()

        return LandingStats(
            views_total=stats["views_total"],
            views_today=stats["views_today"],
            unique_users=stats["unique_users"],
            users_online=users_online,
            avg_session_duration=stats["avg_session_duration"],
            bounce_rate=stats["bounce_rate"],
            conversions=stats["conversions"],
            top_sources=stats["top_sources"],
            timeline=stats.get("timeline", []),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics: {str(e)}"
        )
