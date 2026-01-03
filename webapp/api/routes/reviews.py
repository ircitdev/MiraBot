"""
Reviews API endpoints.
Эндпоинты для работы с отзывами пользователей.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from webapp.api.middleware import get_current_admin
from database.repositories.support_review import SupportReviewRepository

router = APIRouter()
review_repo = SupportReviewRepository()


# ============================================
# Pydantic Models
# ============================================

class SupportReviewItem(BaseModel):
    """Элемент списка отзывов (для админки)."""
    id: int
    user_id: Optional[int]
    username: Optional[str]
    age: Optional[int]
    about_self: Optional[str]
    review_text: str
    permission_to_publish: bool
    created_at: datetime
    telegram_message_id: Optional[int]


class SupportReviewsResponse(BaseModel):
    """Ответ API со списком отзывов."""
    total: int
    page: int
    per_page: int
    reviews: List[SupportReviewItem]


class PublicReviewItem(BaseModel):
    """Публичный отзыв (для лендинга)."""
    name: str  # "Александр, 35 лет" или "Аноним"
    about: str
    text: str
    date: str  # "03.01.2026"


# ============================================
# API Endpoints (для админки)
# ============================================

@router.get("/reviews", response_model=SupportReviewsResponse)
async def get_reviews(
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(20, ge=1, le=100, description="Количество на странице"),
    permission: Optional[bool] = Query(None, description="Фильтр по разрешению на публикацию"),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Получить список отзывов с фильтрацией.

    Параметры:
    - page: номер страницы
    - limit: количество отзывов на странице
    - permission: True - только с разрешением, False - только без разрешения, None - все
    """
    reviews, total = await review_repo.get_all_paginated(
        page=page,
        limit=limit,
        permission=permission
    )

    review_items = [
        SupportReviewItem(
            id=review.id,
            user_id=review.user_id,
            username=review.username,
            age=review.age,
            about_self=review.about_self,
            review_text=review.review_text,
            permission_to_publish=review.permission_to_publish,
            created_at=review.created_at,
            telegram_message_id=review.telegram_message_id,
        )
        for review in reviews
    ]

    return SupportReviewsResponse(
        total=total,
        page=page,
        per_page=limit,
        reviews=review_items,
    )


# ============================================
# Public API (без авторизации, для лендинга)
# ============================================

@router.get("/public/reviews", response_model=List[PublicReviewItem])
async def get_public_reviews(
    limit: int = Query(10, ge=1, le=100, description="Количество отзывов"),
):
    """
    Публичный эндпоинт для получения отзывов с разрешением на публикацию.

    Используется на лендинге для отображения отзывов пользователей.
    Возвращает только отзывы с permission_to_publish=True.

    Без авторизации, доступен всем.
    """
    reviews_data = await review_repo.export_to_json(permission=True, limit=limit)

    public_reviews = []

    for review in reviews_data:
        # Форматирование имени
        if review.get("username"):
            name = review["username"]
            if review.get("age"):
                name += f", {review['age']} лет"
        else:
            name = "Аноним"

        # Форматирование даты
        created_at = review.get("created_at")
        if isinstance(created_at, datetime):
            date_str = created_at.strftime("%d.%m.%Y")
        elif isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime("%d.%m.%Y")
            except:
                date_str = created_at
        else:
            date_str = "—"

        public_reviews.append(PublicReviewItem(
            name=name,
            about=review.get("about_self", ""),
            text=review["review_text"],
            date=date_str,
        ))

    return public_reviews
