"""
Programs API endpoints.
Просмотр прогресса в структурированных программах.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository
from database.repositories.program import ProgramRepository

router = APIRouter()
user_repo = UserRepository()
program_repo = ProgramRepository()


class CompletedDay(BaseModel):
    """День, выполненный в программе."""
    day: int
    completed_at: str
    feedback: Optional[str] = None


class ProgramResponse(BaseModel):
    """Информация о программе пользователя."""
    id: int
    program_id: str
    program_name: str
    status: str
    current_day: int
    total_days: int
    progress_percentage: int
    completed_days: List[CompletedDay]
    started_at: Optional[str]
    completed_at: Optional[str]
    reminder_time: Optional[str]
    reminder_enabled: bool


class ProgramsListResponse(BaseModel):
    """Список программ пользователя."""
    programs: List[ProgramResponse]
    total_active: int
    total_completed: int


class ProgressSummary(BaseModel):
    """Общий прогресс по программам."""
    total_programs: int
    completed_programs: int
    active_programs: int
    total_days_completed: int
    current_streak: int  # Дней подряд с выполнением


@router.get("/", response_model=ProgramsListResponse)
async def get_programs(current_user: dict = Depends(get_current_user)):
    """Получить список всех программ пользователя."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    programs = await program_repo.get_all_programs(user.id)

    program_responses = []
    total_active = 0
    total_completed = 0

    for p in programs:
        # Вычисляем процент прогресса
        if p.total_days > 0:
            progress = int((p.current_day - 1) / p.total_days * 100)
            if p.status == "completed":
                progress = 100
        else:
            progress = 0

        # Считаем статистику
        if p.status == "active":
            total_active += 1
        elif p.status == "completed":
            total_completed += 1

        # Преобразуем completed_days
        completed_days_list = []
        if p.completed_days:
            for day_info in p.completed_days:
                completed_days_list.append(CompletedDay(
                    day=day_info.get("day", 0),
                    completed_at=day_info.get("completed_at", ""),
                    feedback=day_info.get("feedback"),
                ))

        program_responses.append(ProgramResponse(
            id=p.id,
            program_id=p.program_id,
            program_name=p.program_name,
            status=p.status,
            current_day=p.current_day,
            total_days=p.total_days,
            progress_percentage=progress,
            completed_days=completed_days_list,
            started_at=p.started_at.isoformat() if p.started_at else None,
            completed_at=p.completed_at.isoformat() if p.completed_at else None,
            reminder_time=p.reminder_time,
            reminder_enabled=p.reminder_enabled,
        ))

    return ProgramsListResponse(
        programs=program_responses,
        total_active=total_active,
        total_completed=total_completed,
    )


@router.get("/progress", response_model=ProgressSummary)
async def get_progress_summary(current_user: dict = Depends(get_current_user)):
    """Получить общую статистику прогресса."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    programs = await program_repo.get_all_programs(user.id)

    total_programs = len(programs)
    completed_programs = sum(1 for p in programs if p.status == "completed")
    active_programs = sum(1 for p in programs if p.status == "active")

    # Считаем общее количество выполненных дней
    total_days_completed = 0
    for p in programs:
        if p.completed_days:
            total_days_completed += len(p.completed_days)

    # Вычисляем текущий streak (дни подряд)
    # Собираем все даты выполнения
    all_completion_dates = []
    for p in programs:
        if p.completed_days:
            for day_info in p.completed_days:
                completed_at = day_info.get("completed_at", "")
                if completed_at:
                    try:
                        dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                        all_completion_dates.append(dt.date())
                    except ValueError:
                        pass

    # Убираем дубликаты и сортируем
    unique_dates = sorted(set(all_completion_dates), reverse=True)

    # Считаем streak
    current_streak = 0
    today = datetime.now().date()

    for i, date in enumerate(unique_dates):
        # Упрощённый подсчёт: просто количество последних дней подряд
        if i == 0 and (date == today or date == today - timedelta(days=1)):
            current_streak = 1
        elif i > 0 and unique_dates[i-1] - date == timedelta(days=1):
            current_streak += 1
        else:
            break

    return ProgressSummary(
        total_programs=total_programs,
        completed_programs=completed_programs,
        active_programs=active_programs,
        total_days_completed=total_days_completed,
        current_streak=current_streak,
    )


@router.get("/{program_entry_id}", response_model=ProgramResponse)
async def get_program_details(
    program_entry_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Получить детали конкретной программы."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    program = await program_repo.get(program_entry_id)

    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    # Проверяем что программа принадлежит пользователю
    if program.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Вычисляем процент прогресса
    if program.total_days > 0:
        progress = int((program.current_day - 1) / program.total_days * 100)
        if program.status == "completed":
            progress = 100
    else:
        progress = 0

    # Преобразуем completed_days
    completed_days_list = []
    if program.completed_days:
        for day_info in program.completed_days:
            completed_days_list.append(CompletedDay(
                day=day_info.get("day", 0),
                completed_at=day_info.get("completed_at", ""),
                feedback=day_info.get("feedback"),
            ))

    return ProgramResponse(
        id=program.id,
        program_id=program.program_id,
        program_name=program.program_name,
        status=program.status,
        current_day=program.current_day,
        total_days=program.total_days,
        progress_percentage=progress,
        completed_days=completed_days_list,
        started_at=program.started_at.isoformat() if program.started_at else None,
        completed_at=program.completed_at.isoformat() if program.completed_at else None,
        reminder_time=program.reminder_time,
        reminder_enabled=program.reminder_enabled,
    )
