"""
Settings API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository

router = APIRouter()
user_repo = UserRepository()


class UserSettings(BaseModel):
    """Модель настроек пользователя."""
    display_name: Optional[str] = None
    persona: Optional[str] = None
    partner_name: Optional[str] = None
    partner_gender: Optional[str] = None
    marriage_years: Optional[int] = None
    timezone: Optional[str] = None
    rituals_enabled: Optional[List[str]] = None
    preferred_time_morning: Optional[str] = None
    preferred_time_evening: Optional[str] = None
    proactive_messages: Optional[bool] = None
    birthday: Optional[date] = None
    anniversary: Optional[date] = None


class UserSettingsResponse(BaseModel):
    """Ответ с настройками."""
    telegram_id: int
    display_name: Optional[str]
    persona: str
    partner_name: Optional[str]
    partner_gender: Optional[str]
    marriage_years: Optional[int]
    timezone: str
    rituals_enabled: List[str]
    preferred_time_morning: Optional[str]
    preferred_time_evening: Optional[str]
    proactive_messages: bool
    birthday: Optional[date]
    anniversary: Optional[date]
    created_at: datetime


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Получить текущие настройки пользователя."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "telegram_id": user.telegram_id,
        "display_name": user.display_name,
        "persona": user.persona or "mira",
        "partner_name": user.partner_name,
        "partner_gender": user.partner_gender,
        "marriage_years": user.marriage_years,
        "timezone": user.timezone,
        "rituals_enabled": user.rituals_enabled or [],
        "preferred_time_morning": user.preferred_time_morning,
        "preferred_time_evening": user.preferred_time_evening,
        "proactive_messages": user.proactive_messages,
        "birthday": user.birthday,
        "anniversary": user.anniversary,
        "created_at": user.created_at,
    }


@router.patch("/")
async def update_settings(
    settings: UserSettings,
    current_user: dict = Depends(get_current_user)
):
    """Обновить настройки пользователя."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем только переданные поля
    update_data = settings.dict(exclude_unset=True)

    if update_data:
        await user_repo.update(user.id, **update_data)

    return {"status": "ok", "updated": list(update_data.keys())}


@router.post("/rituals/{ritual_type}/enable")
async def enable_ritual(
    ritual_type: str,
    current_user: dict = Depends(get_current_user)
):
    """Включить ритуал."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rituals = user.rituals_enabled or []

    if ritual_type not in rituals:
        rituals.append(ritual_type)
        await user_repo.update(user.id, rituals_enabled=rituals)

        # Планируем ритуал
        from services.scheduler import schedule_user_rituals
        await schedule_user_rituals(user.id)

    return {"status": "ok", "ritual": ritual_type, "enabled": True}


@router.post("/rituals/{ritual_type}/disable")
async def disable_ritual(
    ritual_type: str,
    current_user: dict = Depends(get_current_user)
):
    """Отключить ритуал."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rituals = user.rituals_enabled or []

    if ritual_type in rituals:
        rituals.remove(ritual_type)
        await user_repo.update(user.id, rituals_enabled=rituals)

        # Отменяем запланированные
        from services.scheduler import cancel_user_ritual
        ritual_map = {
            "morning": "morning_checkin",
            "evening": "evening_checkin",
        }
        await cancel_user_ritual(user.id, ritual_map.get(ritual_type, ritual_type))

    return {"status": "ok", "ritual": ritual_type, "enabled": False}
