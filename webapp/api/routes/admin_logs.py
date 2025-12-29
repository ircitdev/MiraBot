"""
API эндпоинты для просмотра логов действий администраторов.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from database.repositories.admin_log import AdminLogRepository
from webapp.api.middleware import get_current_admin, require_admin_role


router = APIRouter(prefix="/admin-logs", tags=["admin-logs"])


# === Pydantic Models ===

class AdminLogResponse(BaseModel):
    """Ответ с данными лога."""
    id: int
    admin_user_id: int
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    details: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class LogsListResponse(BaseModel):
    """Ответ со списком логов и метаданными."""
    logs: List[AdminLogResponse]
    total: int
    limit: int
    offset: int


# === Эндпоинты ===

@router.get("/")
async def list_logs(
    admin_user_id: Optional[int] = Query(None, description="Фильтр по админу"),
    action: Optional[str] = Query(None, description="Фильтр по действию"),
    resource_type: Optional[str] = Query(None, description="Фильтр по типу ресурса"),
    resource_id: Optional[int] = Query(None, description="Фильтр по ID ресурса"),
    success: Optional[bool] = Query(None, description="Фильтр по успешности"),
    from_date: Optional[str] = Query(None, description="Начало периода (ISO format)"),
    to_date: Optional[str] = Query(None, description="Конец периода (ISO format)"),
    limit: int = Query(100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    admin_data: dict = Depends(get_current_admin)
) -> LogsListResponse:
    """
    Получить список логов с фильтрацией.

    Модераторы видят только свои логи.
    Администраторы видят все логи.

    Query params:
        - admin_user_id: Фильтр по ID админа
        - action: Фильтр по действию (user_block, subscription_grant, и т.д.)
        - resource_type: Фильтр по типу ресурса (user, subscription, message)
        - resource_id: Фильтр по ID конкретного ресурса
        - success: Фильтр по успешности (true/false)
        - from_date: Начало периода (формат ISO: 2025-12-29T00:00:00)
        - to_date: Конец периода
        - limit: Количество записей (макс 500)
        - offset: Смещение для пагинации
    """
    repo = AdminLogRepository()

    # Модераторы видят только свои логи
    if admin_data["role"] == "moderator":
        admin_user_id = admin_data["admin_id"]

    # Парсим даты
    from_datetime = None
    to_datetime = None

    if from_date:
        try:
            from_datetime = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат from_date")

    if to_date:
        try:
            to_datetime = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат to_date")

    # Получаем логи
    logs = await repo.list_logs(
        admin_user_id=admin_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        success=success,
        from_date=from_datetime,
        to_date=to_datetime,
        limit=limit,
        offset=offset,
    )

    # Получаем общее количество
    total = await repo.count_logs(
        admin_user_id=admin_user_id,
        action=action,
        resource_type=resource_type,
        success=success,
        from_date=from_datetime,
        to_date=to_datetime,
    )

    return LogsListResponse(
        logs=[
            AdminLogResponse(
                id=log.id,
                admin_user_id=log.admin_user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                success=log.success,
                error_message=log.error_message,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/me")
async def get_my_logs(
    action: Optional[str] = Query(None, description="Фильтр по действию"),
    limit: int = Query(50, ge=1, le=200, description="Количество записей"),
    admin_data: dict = Depends(get_current_admin)
) -> List[AdminLogResponse]:
    """
    Получить последние логи текущего администратора/модератора.

    Query params:
        - action: Фильтр по действию (опционально)
        - limit: Количество записей (по умолчанию 50, макс 200)
    """
    repo = AdminLogRepository()

    logs = await repo.get_recent_actions(
        admin_user_id=admin_data["admin_id"],
        limit=limit
    )

    return [
        AdminLogResponse(
            id=log.id,
            admin_user_id=log.admin_user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]


@router.get("/resource/{resource_type}/{resource_id}")
async def get_resource_logs(
    resource_type: str,
    resource_id: int,
    limit: int = Query(50, ge=1, le=200),
    admin_data: dict = Depends(get_current_admin)
) -> List[AdminLogResponse]:
    """
    Получить все действия над конкретным ресурсом.

    Path params:
        - resource_type: Тип ресурса (user, subscription, message, и т.д.)
        - resource_id: ID ресурса

    Query params:
        - limit: Количество записей (по умолчанию 50, макс 200)

    Примеры:
        - GET /admin-logs/resource/user/123 - все действия над пользователем 123
        - GET /admin-logs/resource/subscription/456 - все действия над подпиской 456
    """
    repo = AdminLogRepository()

    logs = await repo.get_actions_by_resource(
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit
    )

    return [
        AdminLogResponse(
            id=log.id,
            admin_user_id=log.admin_user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]


@router.get("/failures")
async def get_failed_actions(
    admin_user_id: Optional[int] = Query(None, description="Фильтр по админу"),
    hours: int = Query(24, ge=1, le=168, description="Период в часах (макс 7 дней)"),
    limit: int = Query(100, ge=1, le=500),
    admin_data: dict = Depends(require_admin_role)
) -> List[AdminLogResponse]:
    """
    Получить неуспешные действия за последние N часов.

    Требует права администратора (role='admin').

    Используется для мониторинга ошибок и проблем в работе модераторов.

    Query params:
        - admin_user_id: Фильтр по админу (опционально)
        - hours: Период в часах (по умолчанию 24, макс 168 = 7 дней)
        - limit: Количество записей (макс 500)
    """
    repo = AdminLogRepository()

    logs = await repo.get_failed_actions(
        admin_user_id=admin_user_id,
        hours=hours,
        limit=limit
    )

    return [
        AdminLogResponse(
            id=log.id,
            admin_user_id=log.admin_user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]


@router.get("/{log_id}")
async def get_log(
    log_id: int,
    admin_data: dict = Depends(get_current_admin)
) -> AdminLogResponse:
    """
    Получить детальную информацию о конкретном логе.

    Path params:
        - log_id: ID лога
    """
    repo = AdminLogRepository()
    log = await repo.get(log_id)

    if not log:
        raise HTTPException(status_code=404, detail="Лог не найден")

    # Модераторы могут видеть только свои логи
    if admin_data["role"] == "moderator" and log.admin_user_id != admin_data["admin_id"]:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return AdminLogResponse(
        id=log.id,
        admin_user_id=log.admin_user_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        details=log.details,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        success=log.success,
        error_message=log.error_message,
        created_at=log.created_at.isoformat(),
    )
