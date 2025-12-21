"""
Promo code API endpoints for users.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository
from database.repositories.promo import promo_repo


router = APIRouter()
user_repo = UserRepository()


class ApplyPromoRequest(BaseModel):
    """Запрос на применение промо-кода."""
    code: str


class ApplyPromoResponse(BaseModel):
    """Ответ на применение промо-кода."""
    success: bool
    message: str
    promo_type: Optional[str] = None
    value: Optional[int] = None
    free_days: Optional[int] = None


class ValidatePromoResponse(BaseModel):
    """Ответ на валидацию промо-кода."""
    valid: bool
    error: Optional[str] = None
    promo_type: Optional[str] = None
    value: Optional[int] = None
    description: Optional[str] = None


@router.post("/apply", response_model=ApplyPromoResponse)
async def apply_promo_code(
    request: ApplyPromoRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Применить промо-код.

    Типы промо-кодов:
    - free_days: Добавляет бесплатные дни Premium
    - free_trial: Активирует триал
    - discount_percent: Скидка в процентах (применяется при оплате)
    - discount_amount: Фиксированная скидка (применяется при оплате)
    """
    # Получаем пользователя
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Применяем промо-код
    result = await promo_repo.apply(
        code=request.code.strip().upper(),
        user_id=user.id,
    )

    if not result["success"]:
        return ApplyPromoResponse(
            success=False,
            message=result["error"] or "Не удалось применить промо-код",
        )

    # Формируем сообщение в зависимости от типа
    promo_result = result["result"]
    promo_type = promo_result["type"]
    value = promo_result["value"]

    if promo_type == "free_days":
        message = f"Промо-код применён! Добавлено {value} дней Premium"
    elif promo_type == "free_trial":
        message = f"Промо-код применён! Активирован триал на {value} дней"
    elif promo_type == "discount_percent":
        message = f"Промо-код применён! Скидка {value}% будет применена при следующей оплате"
    elif promo_type == "discount_amount":
        message = f"Промо-код применён! Скидка {value}₽ будет применена при следующей оплате"
    else:
        message = "Промо-код успешно применён!"

    return ApplyPromoResponse(
        success=True,
        message=message,
        promo_type=promo_type,
        value=value,
        free_days=promo_result.get("free_days"),
    )


@router.post("/validate", response_model=ValidatePromoResponse)
async def validate_promo_code(
    request: ApplyPromoRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Проверить валидность промо-кода без применения.
    """
    # Получаем пользователя
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Валидируем промо-код
    result = await promo_repo.validate(
        code=request.code.strip().upper(),
        user_id=user.id,
    )

    if not result["valid"]:
        return ValidatePromoResponse(
            valid=False,
            error=result["error"],
        )

    promo = result["promo"]

    return ValidatePromoResponse(
        valid=True,
        promo_type=promo.promo_type,
        value=promo.value,
        description=promo.description,
    )
