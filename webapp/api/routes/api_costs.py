"""
API эндпоинты для просмотра расходов на API (Claude, Yandex, OpenAI).
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from database.repositories.api_cost import ApiCostRepository
from webapp.api.middleware import get_current_admin


router = APIRouter(prefix="/api-costs", tags=["api-costs"])


# === Pydantic Models ===

class ApiCostSummary(BaseModel):
    """Сводка расходов по пользователю."""
    user_id: int
    telegram_id: int
    display_name: Optional[str]
    total_cost: float


class ApiCostByProvider(BaseModel):
    """Расходы по провайдеру."""
    provider: str
    total_cost: float


class ApiCostByDate(BaseModel):
    """Расходы по дате."""
    date: str
    provider: str
    total_cost: float
    total_tokens: int


class ApiCostStats(BaseModel):
    """Общая статистика расходов."""
    total_cost: float
    total_tokens: int
    by_provider: dict
    unique_users: int


# === Эндпоинты ===

@router.get("/users/summary")
async def get_users_api_costs_summary(
    admin_data: dict = Depends(get_current_admin)
) -> List[ApiCostSummary]:
    """
    Получить сводку расходов на API для всех пользователей.

    Returns:
        Список пользователей с общими расходами (отсортировано по убыванию расходов)
    """
    repo = ApiCostRepository()
    costs = await repo.get_all_users_total_costs()

    return [
        ApiCostSummary(
            user_id=cost['user_id'],
            telegram_id=cost['telegram_id'],
            display_name=cost['display_name'],
            total_cost=cost['total_cost']
        )
        for cost in costs
    ]


@router.get("/users/{telegram_id}")
async def get_user_api_costs(
    telegram_id: int,
    admin_data: dict = Depends(get_current_admin)
) -> dict:
    """
    Получить детальную информацию о расходах пользователя на API.

    Path params:
        - telegram_id: Telegram ID пользователя

    Returns:
        {
            "total_cost": float,
            "by_provider": {"claude": 0.123, "yandex_tts": 0.001, ...}
        }
    """
    from database.repositories.user import UserRepository
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        return {"total_cost": 0.0, "by_provider": {}}

    repo = ApiCostRepository()
    total_cost = await repo.get_total_cost_by_user(user.id)
    by_provider = await repo.get_costs_by_provider(user.id)

    return {
        "total_cost": total_cost,
        "by_provider": by_provider
    }


@router.get("/stats")
async def get_api_costs_stats(
    from_date: Optional[str] = Query(None, description="Начало периода (ISO format YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Конец периода (ISO format YYYY-MM-DD)"),
    admin_data: dict = Depends(get_current_admin)
) -> ApiCostStats:
    """
    Получить общую статистику расходов на API.

    Query params:
        - from_date: Начало периода (опционально, формат YYYY-MM-DD)
        - to_date: Конец периода (опционально, формат YYYY-MM-DD)

    Returns:
        Статистика: общая стоимость, токены, расходы по провайдерам, количество пользователей
    """
    repo = ApiCostRepository()

    from_datetime = None
    to_datetime = None

    if from_date:
        from_datetime = datetime.fromisoformat(from_date)
    if to_date:
        to_datetime = datetime.fromisoformat(to_date)

    stats = await repo.get_stats_summary(
        from_date=from_datetime,
        to_date=to_datetime
    )

    return ApiCostStats(
        total_cost=stats['total_cost'],
        total_tokens=stats['total_tokens'],
        by_provider=stats['by_provider'],
        unique_users=stats['unique_users']
    )


@router.get("/by-date")
async def get_api_costs_by_date(
    from_date: Optional[str] = Query(None, description="Начало периода (ISO format YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Конец периода (ISO format YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="Фильтр по user_id"),
    provider: Optional[str] = Query(None, description="Фильтр по провайдеру (claude, yandex_tts, etc.)"),
    admin_data: dict = Depends(get_current_admin)
) -> List[ApiCostByDate]:
    """
    Получить расходы по датам для графика.

    Query params:
        - from_date: Начало периода (опционально, формат YYYY-MM-DD)
        - to_date: Конец периода (опционально, формат YYYY-MM-DD)
        - user_id: Фильтр по конкретному пользователю (опционально)
        - provider: Фильтр по провайдеру (опционально)

    Returns:
        Список расходов по датам и провайдерам
    """
    repo = ApiCostRepository()

    from_datetime = None
    to_datetime = None

    # Если даты не указаны, берём последние 30 дней
    if not from_date:
        from_datetime = datetime.now() - timedelta(days=30)
    else:
        from_datetime = datetime.fromisoformat(from_date)

    if to_date:
        to_datetime = datetime.fromisoformat(to_date)

    costs = await repo.get_costs_by_date(
        from_date=from_datetime,
        to_date=to_datetime,
        user_id=user_id,
        provider=provider
    )

    return [
        ApiCostByDate(
            date=cost['date'],
            provider=cost['provider'],
            total_cost=cost['total_cost'],
            total_tokens=cost['total_tokens']
        )
        for cost in costs
    ]


@router.get("/top-users")
async def get_top_users_by_api_costs(
    limit: int = Query(10, ge=1, le=100, description="Количество пользователей"),
    from_date: Optional[str] = Query(None, description="Начало периода (ISO format YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Конец периода (ISO format YYYY-MM-DD)"),
    admin_data: dict = Depends(get_current_admin)
) -> List[dict]:
    """
    Получить топ пользователей по расходам на API.

    Query params:
        - limit: Количество пользователей в топе (по умолчанию 10, макс 100)
        - from_date: Начало периода (опционально, формат YYYY-MM-DD)
        - to_date: Конец периода (опционально, формат YYYY-MM-DD)

    Returns:
        Список топ пользователей с расходами
    """
    repo = ApiCostRepository()

    from_datetime = None
    to_datetime = None

    if from_date:
        from_datetime = datetime.fromisoformat(from_date)
    if to_date:
        to_datetime = datetime.fromisoformat(to_date)

    top_users = await repo.get_top_users_by_cost(
        limit=limit,
        from_date=from_datetime,
        to_date=to_datetime
    )

    return top_users
