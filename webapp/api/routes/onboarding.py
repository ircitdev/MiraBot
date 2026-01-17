"""
API роуты для аналитики онбординга.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from webapp.api.middleware import get_current_admin
from database.repositories.onboarding_event import OnboardingEventRepository


router = APIRouter()
onboarding_repo = OnboardingEventRepository()


class DropoffPoint(BaseModel):
    """Точка отсева в воронке."""
    step: str = Field(..., description="Название шага")
    reached: int = Field(..., description="Количество пользователей, достигших этого шага")
    completed_next: int = Field(..., description="Количество пользователей, завершивших следующий шаг")
    dropoff_rate: float = Field(..., description="Процент отсева")


class AIParsingStats(BaseModel):
    """Статистика успешности AI-парсинга."""
    social_portrait_success_rate: float = Field(..., description="% успешности парсинга социального портрета")
    family_details_success_rate: float = Field(..., description="% успешности парсинга семейных данных")


class OnboardingFunnelStats(BaseModel):
    """Статистика воронки онбординга."""
    funnel: Dict[str, int] = Field(..., description="Количество пользователей на каждом шаге")
    dropoff_points: List[DropoffPoint] = Field(..., description="Точки отсева")
    ai_parsing: AIParsingStats = Field(..., description="Статистика AI-парсинга")
    total_started: int = Field(..., description="Всего начали онбординг")
    total_completed: int = Field(..., description="Всего завершили онбординг")
    completion_rate: float = Field(..., description="Процент завершения онбординга")


@router.get("/onboarding/funnel", response_model=OnboardingFunnelStats)
async def get_onboarding_funnel(
    admin_data: dict = Depends(get_current_admin)
):
    """
    Получить статистику воронки онбординга.

    Args:
        admin_data: Данные администратора (из middleware)

    Returns:
        OnboardingFunnelStats с метриками онбординга
    """
    try:
        # Получаем статистику воронки
        funnel_stats = await onboarding_repo.get_onboarding_funnel_stats()

        # Получаем точки отсева
        dropoff_data = await onboarding_repo.get_dropoff_points()

        # Получаем статистику AI-парсинга
        ai_parsing = await onboarding_repo.get_ai_parsing_success_rate()

        # Вычисляем общие показатели
        total_started = funnel_stats.get("onboarding_started", 0)
        total_completed = funnel_stats.get("onboarding_completed", 0)
        completion_rate = (total_completed / total_started * 100) if total_started > 0 else 0

        return OnboardingFunnelStats(
            funnel=funnel_stats,
            dropoff_points=[
                DropoffPoint(**point) for point in dropoff_data
            ],
            ai_parsing=AIParsingStats(**ai_parsing),
            total_started=total_started,
            total_completed=total_completed,
            completion_rate=round(completion_rate, 2)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get onboarding funnel stats: {str(e)}"
        )
