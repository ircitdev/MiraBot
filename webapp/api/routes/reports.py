"""
API эндпоинты для работы с AI-отчётами пользователей.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.repositories.user_report import UserReportRepository
from webapp.api.middleware import get_current_admin
from webapp.api.decorators import log_admin_action


router = APIRouter(prefix="/reports", tags=["reports"])


# === Pydantic Models ===

class ReportResponse(BaseModel):
    """Ответ с данными отчёта."""
    id: int
    telegram_id: int
    content: str
    created_by: int | None
    created_at: str

    class Config:
        from_attributes = True


class CreateReportRequest(BaseModel):
    """Запрос на создание отчёта."""
    content: str


# === Эндпоинты ===

@router.get("/{telegram_id}")
async def list_user_reports(
    telegram_id: int,
    admin_data: dict = Depends(get_current_admin)
) -> List[ReportResponse]:
    """
    Получить все отчёты пользователя.

    Path params:
        - telegram_id: Telegram ID пользователя

    Returns:
        Список отчётов, отсортированный по дате (новые первыми)
    """
    repo = UserReportRepository()
    reports = await repo.list_by_user(telegram_id=telegram_id)

    return [
        ReportResponse(
            id=report.id,
            telegram_id=report.telegram_id,
            content=report.content,
            created_by=report.created_by,
            created_at=report.created_at.isoformat(),
        )
        for report in reports
    ]


@router.post("/{telegram_id}")
@log_admin_action(action="report_create", resource_type="report")
async def create_user_report(
    telegram_id: int,
    request: CreateReportRequest,
    admin_data: dict = Depends(get_current_admin)
) -> ReportResponse:
    """
    Создать новый отчёт для пользователя.

    Path params:
        - telegram_id: Telegram ID пользователя

    Body:
        - content: Текст AI-сводки

    Returns:
        Созданный отчёт
    """
    repo = UserReportRepository()

    report = await repo.create(
        telegram_id=telegram_id,
        content=request.content,
        created_by=admin_data["admin_id"]
    )

    return ReportResponse(
        id=report.id,
        telegram_id=report.telegram_id,
        content=report.content,
        created_by=report.created_by,
        created_at=report.created_at.isoformat(),
    )


@router.delete("/{report_id}")
@log_admin_action(action="report_delete", resource_type="report")
async def delete_report(
    report_id: int,
    admin_data: dict = Depends(get_current_admin)
) -> dict:
    """
    Удалить отчёт.

    Path params:
        - report_id: ID отчёта

    Returns:
        Статус удаления
    """
    repo = UserReportRepository()

    success = await repo.delete(report_id=report_id)

    if not success:
        raise HTTPException(status_code=404, detail="Отчёт не найден")

    return {"success": True, "message": "Отчёт удалён"}
