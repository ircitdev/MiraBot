"""
Support API endpoints.
Эндпоинты для работы с обращениями в техническую поддержку.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from webapp.api.middleware import get_current_admin
from database.repositories.support_user import SupportUserRepository
from database.repositories.support_message import SupportMessageRepository

router = APIRouter()
user_repo = SupportUserRepository()
message_repo = SupportMessageRepository()


# ============================================
# Pydantic Models
# ============================================

class SupportUserItem(BaseModel):
    """Элемент списка обращений пользователя."""
    user_id: int
    telegram_id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    photo_url: Optional[str]
    topic_id: int
    total_messages: int
    last_message_date: Optional[datetime]
    last_message_text: Optional[str]
    is_bot_blocked: bool


class SupportQuestionsResponse(BaseModel):
    """Ответ API со списком обращений."""
    total: int
    page: int
    per_page: int
    questions: List[SupportUserItem]


class SupportMessageItem(BaseModel):
    """Элемент истории сообщений."""
    id: int
    sender_type: str  # "user" | "admin"
    message_text: Optional[str]
    media_type: str
    media_file_id: Optional[str]
    created_at: datetime


class SupportMessagesResponse(BaseModel):
    """Ответ API с историей сообщений."""
    total: int
    page: int
    per_page: int
    messages: List[SupportMessageItem]
    user_info: SupportUserItem


# ============================================
# API Endpoints
# ============================================

@router.get("/questions", response_model=SupportQuestionsResponse)
async def get_questions(
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(20, ge=1, le=100, description="Количество на странице"),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Получить список всех обращений в поддержку с пагинацией.

    Возвращает список пользователей, которые обращались в поддержку,
    отсортированный по дате последнего сообщения (сначала новые).
    """
    # Получить всех пользователей поддержки
    users, total = await user_repo.get_all_paginated(page=page, limit=limit)

    questions = []

    for user in users:
        # Получить количество сообщений пользователя
        total_messages = await message_repo.count_by_user(user.id)

        # Получить последнее сообщение
        last_message_date = await message_repo.get_last_message_date(user.id)

        # Получить текст последнего сообщения
        last_messages, _ = await message_repo.get_by_user(user.id, page=1, limit=1)
        last_message_text = last_messages[0].message_text if last_messages else None

        questions.append(SupportUserItem(
            user_id=user.id,
            telegram_id=user.telegram_id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            photo_url=user.photo_url,
            topic_id=user.topic_id,
            total_messages=total_messages,
            last_message_date=last_message_date,
            last_message_text=last_message_text,
            is_bot_blocked=user.is_bot_blocked,
        ))

    return SupportQuestionsResponse(
        total=total,
        page=page,
        per_page=limit,
        questions=questions,
    )


@router.get("/questions/{user_id}/messages", response_model=SupportMessagesResponse)
async def get_user_messages(
    user_id: int,
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(50, ge=1, le=200, description="Количество сообщений"),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Получить историю сообщений конкретного пользователя.

    Возвращает все сообщения между пользователем и поддержкой,
    отсортированные по дате создания (сначала старые).
    """
    # Проверить существование пользователя
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить сообщения
    messages, total = await message_repo.get_by_user(user_id, page=page, limit=limit)

    # Подготовить информацию о пользователе
    user_info = SupportUserItem(
        user_id=user.id,
        telegram_id=user.telegram_id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        photo_url=user.photo_url,
        topic_id=user.topic_id,
        total_messages=total,
        last_message_date=await message_repo.get_last_message_date(user.id),
        last_message_text=None,
        is_bot_blocked=user.is_bot_blocked,
    )

    message_items = [
        SupportMessageItem(
            id=msg.id,
            sender_type=msg.sender_type,
            message_text=msg.message_text,
            media_type=msg.media_type,
            media_file_id=msg.media_file_id,
            created_at=msg.created_at,
        )
        for msg in messages
    ]

    return SupportMessagesResponse(
        total=total,
        page=page,
        per_page=limit,
        messages=message_items,
        user_info=user_info,
    )
