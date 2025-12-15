"""
Referral API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository
from services.referral import ReferralService


router = APIRouter()
user_repo = UserRepository()
referral_service = ReferralService()


class ReferralCodeResponse(BaseModel):
    """Ответ с реферальным кодом."""
    code: str
    link: str


class ReferralStatsResponse(BaseModel):
    """Статистика рефералов."""
    invited_count: int
    bonus_earned_days: int
    next_milestone: int
    milestone_progress: float


@router.get("/code", response_model=ReferralCodeResponse)
async def get_referral_code(current_user: dict = Depends(get_current_user)):
    """Получить реферальный код текущего пользователя."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить или создать код
    code = await referral_service.get_or_create_code(user.id)

    # Сформировать ссылку
    from config.settings import settings
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'mira_support_bot')
    link = f"https://t.me/{bot_username}?start={code}"

    return {
        "code": code,
        "link": link
    }


@router.get("/stats", response_model=ReferralStatsResponse)
async def get_referral_stats(current_user: dict = Depends(get_current_user)):
    """Получить статистику рефералов."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить статистику
    stats = await referral_service.get_stats(user.id)

    # Рассчитать прогресс к следующему milestone (каждые 3 приглашения)
    invited_count = stats.get("invited_count", 0)
    milestone_progress = min((invited_count % 3) / 3.0 * 100, 100)
    next_milestone = 3 - (invited_count % 3)

    return {
        "invited_count": invited_count,
        "bonus_earned_days": stats.get("bonus_earned_days", 0),
        "next_milestone": next_milestone,
        "milestone_progress": milestone_progress
    }
