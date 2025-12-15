"""
Export API endpoints.
"""

import io
import csv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.mood import MoodRepository


router = APIRouter()
user_repo = UserRepository()
conv_repo = ConversationRepository()
mood_repo = MoodRepository()


@router.get("/history")
async def export_history(current_user: dict = Depends(get_current_user)):
    """Экспорт истории сообщений пользователя в CSV."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить все сообщения
    messages, _ = await conv_repo.get_paginated(user.id, page=1, per_page=10000)

    # Создать CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата", "Роль", "Сообщение", "Тип", "Теги"])

    for msg in reversed(messages):  # В хронологическом порядке
        writer.writerow([
            msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "Вы" if msg.role == "user" else "Мира",
            msg.content,
            msg.message_type or "text",
            ", ".join(msg.tags) if msg.tags else ""
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=mira_history_{user.telegram_id}.csv"
        }
    )


@router.get("/stats")
async def export_stats(current_user: dict = Depends(get_current_user)):
    """Экспорт статистики настроения в CSV."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить записи настроения
    moods = await mood_repo.get_user_moods(user.id, limit=1000)

    # Создать CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата", "Настроение (балл)", "Основная эмоция", "Энергия", "Тревожность"])

    for mood in moods:
        writer.writerow([
            mood.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            mood.mood_score,
            mood.primary_emotion or "",
            mood.energy_level or "",
            mood.anxiety_level or ""
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=mira_mood_{user.telegram_id}.csv"
        }
    )
