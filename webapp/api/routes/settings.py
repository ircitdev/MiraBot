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

    # Новые поля
    topics_avoided: Optional[List[str]] = None
    content_preferences: Optional[dict] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


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

    # Новые поля
    topics_avoided: List[str]
    content_preferences: dict
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Получить текущие настройки пользователя."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Извлечь topics_avoided из communication_style
    comm_style = user.communication_style or {}
    topics_avoided = comm_style.get("topics_avoided", [])

    # Форматировать quiet_hours
    quiet_start = user.quiet_hours_start.strftime("%H:%M") if user.quiet_hours_start else None
    quiet_end = user.quiet_hours_end.strftime("%H:%M") if user.quiet_hours_end else None

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
        "topics_avoided": topics_avoided,
        "content_preferences": user.content_preferences or {},
        "quiet_hours_start": quiet_start,
        "quiet_hours_end": quiet_end,
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

    # Обработать topics_avoided - сохранить в communication_style
    if "topics_avoided" in update_data:
        comm_style = user.communication_style or {}
        comm_style["topics_avoided"] = update_data.pop("topics_avoided")
        comm_style["updated_at"] = datetime.now().isoformat()
        update_data["communication_style"] = comm_style

    # Обработать quiet_hours - конвертировать строки в time
    if "quiet_hours_start" in update_data and update_data["quiet_hours_start"]:
        from datetime import time as dt_time
        hour, minute = map(int, update_data["quiet_hours_start"].split(":"))
        update_data["quiet_hours_start"] = dt_time(hour, minute)

    if "quiet_hours_end" in update_data and update_data["quiet_hours_end"]:
        from datetime import time as dt_time
        hour, minute = map(int, update_data["quiet_hours_end"].split(":"))
        update_data["quiet_hours_end"] = dt_time(hour, minute)

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


@router.post("/delete")
async def request_account_deletion(current_user: dict = Depends(get_current_user)):
    """
    Запросить удаление аккаунта.

    Аккаунт помечается на удаление и будет удалён через 3 дня.
    Пользователь может восстановить аккаунт в течение этого периода.
    """
    from datetime import timedelta
    from database.repositories.admin_log import AdminLogRepository
    from loguru import logger

    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Помечаем аккаунт на удаление через 3 дня
    deletion_date = datetime.utcnow() + timedelta(days=3)

    await user_repo.update(
        user.id,
        deletion_requested_at=datetime.utcnow(),
        deletion_scheduled_for=deletion_date,
    )

    # Логируем в admin logs
    try:
        admin_log_repo = AdminLogRepository()
        await admin_log_repo.create(
            admin_user_id=1,  # Системное событие
            action="account_deletion_request",
            resource_type="user",
            resource_id=user.telegram_id,
            details={
                "deletion_scheduled_for": deletion_date.isoformat(),
                "requested_via": "webapp",
                "username": user.username,
                "first_name": user.first_name,
            },
            success=True,
        )
    except Exception as e:
        logger.warning(f"Failed to log account deletion request: {e}")

    return {
        "success": True,
        "message": "Аккаунт помечен на удаление. У тебя есть 3 дня для восстановления.",
        "deletion_date": deletion_date.isoformat(),
    }
