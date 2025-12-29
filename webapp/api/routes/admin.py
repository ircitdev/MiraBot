"""
Admin API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select, func, desc

from webapp.api.auth import get_current_user
from webapp.api.middleware import get_current_admin
from webapp.api.decorators import log_admin_action, log_critical_action
from database.repositories.user import UserRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.mood import MoodRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.promo import PromoRepository
from database.repositories.profile import profile_repo
from config.settings import settings


router = APIRouter()
user_repo = UserRepository()
conv_repo = ConversationRepository()
mood_repo = MoodRepository()
subscription_repo = SubscriptionRepository()
promo_repo = PromoRepository()


# Список админов (telegram_id)
ADMIN_IDS = [
    getattr(settings, 'ADMIN_TELEGRAM_ID', 0),
    65876198,  # Добавлен админ
]


def is_admin(current_user: dict) -> bool:
    """Проверить является ли пользователь админом."""
    return current_user["user_id"] in ADMIN_IDS


async def require_admin(current_user: dict = Depends(get_current_user)):
    """Dependency для проверки прав админа."""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Access denied. Admin only.")
    return current_user


class UserListItem(BaseModel):
    """Элемент списка пользователей."""
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    display_name: Optional[str]
    avatar_url: Optional[str]
    subscription_plan: str
    subscription_expires_at: Optional[datetime]
    total_messages: int
    last_active_at: Optional[datetime]
    created_at: datetime
    onboarding_completed: bool


class UserDetailResponse(BaseModel):
    """Детальная информация о пользователе."""
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    display_name: Optional[str]
    avatar_url: Optional[str]
    persona: str
    subscription_plan: str
    subscription_expires_at: Optional[datetime]
    total_messages: int
    messages_this_week: int
    last_active_at: Optional[datetime]
    created_at: datetime
    onboarding_completed: bool
    is_blocked: bool
    block_reason: Optional[str]
    partner_name: Optional[str]
    rituals_enabled: List[str]
    proactive_messages: bool


class SystemStatsResponse(BaseModel):
    """Системная статистика."""
    total_users: int
    active_users_today: int
    active_users_week: int
    active_users_month: int
    total_messages: int
    messages_today: int
    messages_week: int
    messages_month: int
    premium_users: int
    trial_users: int
    free_users: int


@router.get("/users", response_model=List[UserListItem])
async def list_users(
    _admin: dict = Depends(require_admin),
    search: Optional[str] = None,
    subscription: Optional[str] = None,
    active_days: Optional[int] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Получить список пользователей с фильтрацией."""
    # TODO: Реализовать фильтрацию в UserRepository
    # Пока возвращаем простой список

    from database.session import get_session_context
    from database.models import User
    from sqlalchemy import select, func

    async with get_session_context() as session:
        query = select(User).order_by(User.created_at.desc())

        # Фильтр по поиску
        if search:
            query = query.where(
                (User.username.contains(search)) |
                (User.first_name.contains(search)) |
                (User.display_name.contains(search))
            )

        # Фильтр по подписке
        if subscription:
            # Получить подписки отдельным запросом
            pass

        # Пагинация
        query = query.limit(limit).offset(offset)

        result = await session.execute(query)
        users = result.scalars().all()

        # Получить количество сообщений для каждого
        user_list = []
        for user in users:
            total_messages = await conv_repo.count_by_user(user.id)

            # Получить подписку
            subscription = await subscription_repo.get_active(user.id)
            sub_plan = subscription.plan if subscription else "free"
            sub_expires = subscription.expires_at if subscription else None

            user_list.append({
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "subscription_plan": sub_plan,
                "subscription_expires_at": sub_expires,
                "total_messages": total_messages,
                "last_active_at": user.last_active_at,
                "created_at": user.created_at,
                "onboarding_completed": user.onboarding_completed,
            })

        return user_list


@router.get("/users/{telegram_id}", response_model=UserDetailResponse)
async def get_user_detail(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """Получить детальную информацию о пользователе."""
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Статистика сообщений
    total_messages = await conv_repo.count_by_user(user.id)

    # Сообщения за неделю
    week_ago = datetime.now() - timedelta(days=7)
    messages_week = await conv_repo.count_by_user_since(user.id, week_ago)

    # Подписка
    subscription = await subscription_repo.get_active(user.id)
    sub_plan = subscription.plan if subscription else "free"
    sub_expires = subscription.expires_at if subscription else None

    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "persona": user.persona or "mira",
        "subscription_plan": sub_plan,
        "subscription_expires_at": sub_expires,
        "total_messages": total_messages,
        "messages_this_week": messages_week,
        "last_active_at": user.last_active_at,
        "created_at": user.created_at,
        "onboarding_completed": user.onboarding_completed,
        "is_blocked": user.is_blocked,
        "block_reason": user.block_reason,
        "partner_name": user.partner_name,
        "rituals_enabled": user.rituals_enabled or [],
        "proactive_messages": user.proactive_messages,
    }


@router.post("/users/{telegram_id}/subscription")
@log_admin_action(action="subscription_grant", resource_type="subscription")
async def update_user_subscription(
    telegram_id: int,
    plan: str,
    days: int,
    admin_data: dict = Depends(get_current_admin),
):
    """Обновить подписку пользователя."""
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Создать или обновить подписку
    from services.subscription import SubscriptionService

    sub_service = SubscriptionService()

    expires_at = datetime.now() + timedelta(days=days)

    # Получить активную подписку
    current_sub = await subscription_repo.get_active(user.id)

    if current_sub:
        # Обновить существующую
        await subscription_repo.update(
            current_sub.id,
            plan=plan,
            expires_at=expires_at,
        )
    else:
        # Создать новую
        await subscription_repo.create(
            user_id=user.id,
            plan=plan,
            expires_at=expires_at,
        )

    return {
        "status": "ok",
        "user_id": user.id,
        "plan": plan,
        "expires_at": expires_at,
        "resource_id": telegram_id,
    }


@router.post("/users/{telegram_id}/block")
@log_critical_action(action="user_block", resource_type="user")
async def block_user(
    telegram_id: int,
    reason: str,
    admin_data: dict = Depends(get_current_admin),
):
    """Заблокировать пользователя."""
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await user_repo.update(
        user.id,
        is_blocked=True,
        block_reason=reason,
    )

    return {"status": "ok", "user_id": user.id, "blocked": True, "resource_id": telegram_id}


@router.post("/users/{telegram_id}/unblock")
@log_admin_action(action="user_unblock", resource_type="user")
async def unblock_user(
    telegram_id: int,
    admin_data: dict = Depends(get_current_admin),
):
    """Разблокировать пользователя."""
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await user_repo.update(
        user.id,
        is_blocked=False,
        block_reason=None,
    )

    return {"status": "ok", "user_id": user.id, "blocked": False, "resource_id": telegram_id}


class AdminMessageRequest(BaseModel):
    """Запрос на отправку сообщения от админа."""
    message: str


@router.delete("/users/{telegram_id}")
@log_critical_action(action="user_delete", resource_type="user")
async def delete_user(
    telegram_id: int,
    admin_data: dict = Depends(get_current_admin),
):
    """
    Удалить пользователя и все его данные.

    Удаляет:
    - Профиль пользователя
    - Историю переписки
    - Записи настроения
    - Подписки
    - Память
    - Файлы
    """
    from database.session import get_session_context
    from database.models import User, Message, MoodEntry, Subscription, MemoryEntry, UserFile
    from sqlalchemy import delete

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = user.id

    async with get_session_context() as session:
        # Удаляем связанные данные
        await session.execute(delete(Message).where(Message.user_id == user_id))
        await session.execute(delete(MoodEntry).where(MoodEntry.user_id == user_id))
        await session.execute(delete(Subscription).where(Subscription.user_id == user_id))
        await session.execute(delete(MemoryEntry).where(MemoryEntry.user_id == user_id))
        await session.execute(delete(UserFile).where(UserFile.user_id == user_id))

        # Удаляем самого пользователя
        await session.execute(delete(User).where(User.id == user_id))

        await session.commit()

    return {
        "status": "ok",
        "message": f"Пользователь {telegram_id} и все его данные удалены",
        "resource_id": telegram_id,
    }


@router.post("/users/{telegram_id}/message")
async def send_admin_message(
    telegram_id: int,
    request: AdminMessageRequest,
    _admin: dict = Depends(require_admin),
):
    """
    Отправить персональное сообщение пользователю от имени админа.

    Сообщение будет оформлено как цитата с пометкой "Сообщение от админа".
    """
    import httpx

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Формируем сообщение с пометкой админа
    formatted_message = (
        "📬 *Сообщение от администратора:*\n\n"
        f"_{request.message}_"
    )

    # Отправляем через Telegram API напрямую
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": formatted_message,
                    "parse_mode": "Markdown"
                },
                timeout=10.0
            )
            result = response.json()

            if not result.get("ok"):
                error_desc = result.get("description", "Unknown error")
                raise HTTPException(
                    status_code=500,
                    detail=f"Telegram API error: {error_desc}"
                )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось отправить сообщение: {str(e)}"
        )

    return {
        "status": "ok",
        "message": f"Сообщение отправлено пользователю {telegram_id}",
    }


@router.get("/stats/system", response_model=SystemStatsResponse)
async def get_system_stats(
    _admin: dict = Depends(require_admin),
):
    """Получить системную статистику."""
    from database.session import get_session_context
    from database.models import User, Message
    from sqlalchemy import select, func

    async with get_session_context() as session:
        # Всего пользователей
        total_users_result = await session.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0

        # Активные сегодня
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today_result = await session.execute(
            select(func.count(User.id)).where(User.last_active_at >= today_start)
        )
        active_today = active_today_result.scalar() or 0

        # Активные за неделю
        week_ago = datetime.now() - timedelta(days=7)
        active_week_result = await session.execute(
            select(func.count(User.id)).where(User.last_active_at >= week_ago)
        )
        active_week = active_week_result.scalar() or 0

        # Активные за месяц
        month_ago = datetime.now() - timedelta(days=30)
        active_month_result = await session.execute(
            select(func.count(User.id)).where(User.last_active_at >= month_ago)
        )
        active_month = active_month_result.scalar() or 0

        # Всего сообщений
        total_messages_result = await session.execute(
            select(func.count(Message.id))
        )
        total_messages = total_messages_result.scalar() or 0

        # Сообщения сегодня
        messages_today_result = await session.execute(
            select(func.count(Message.id)).where(Message.created_at >= today_start)
        )
        messages_today = messages_today_result.scalar() or 0

        # Сообщения за неделю
        messages_week_result = await session.execute(
            select(func.count(Message.id)).where(Message.created_at >= week_ago)
        )
        messages_week = messages_week_result.scalar() or 0

        # Сообщения за месяц
        messages_month_result = await session.execute(
            select(func.count(Message.id)).where(Message.created_at >= month_ago)
        )
        messages_month = messages_month_result.scalar() or 0

    # Подписки (требует подсчета через SubscriptionRepository)
    # Пока заглушки
    premium_users = 0
    trial_users = 0
    free_users = total_users

    return {
        "total_users": total_users,
        "active_users_today": active_today,
        "active_users_week": active_week,
        "active_users_month": active_month,
        "total_messages": total_messages,
        "messages_today": messages_today,
        "messages_week": messages_week,
        "messages_month": messages_month,
        "premium_users": premium_users,
        "trial_users": trial_users,
        "free_users": free_users,
    }


class TopActiveUserItem(BaseModel):
    """Элемент списка TOP активных пользователей."""
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_premium: bool
    messages_this_week: int
    mood_emoji: Optional[str] = None
    primary_emotion: Optional[str] = None


@router.get("/stats/top-active", response_model=List[TopActiveUserItem])
async def get_top_active_users(
    _admin: dict = Depends(require_admin),
    limit: int = Query(10, ge=1, le=50),
):
    """Получить TOP активных пользователей за неделю."""
    from database.session import get_session_context
    from database.models import User, Message, Subscription
    from sqlalchemy import select, func, desc
    from sqlalchemy.orm import joinedload

    week_ago = datetime.now() - timedelta(days=7)

    async with get_session_context() as session:
        # Подзапрос для подсчёта сообщений за неделю
        subquery = (
            select(
                Message.user_id,
                func.count(Message.id).label("messages_count")
            )
            .where(Message.created_at >= week_ago)
            .where(Message.role == "user")
            .group_by(Message.user_id)
            .subquery()
        )

        # Основной запрос с JOIN
        query = (
            select(User, subquery.c.messages_count)
            .outerjoin(subquery, User.id == subquery.c.user_id)
            .where(subquery.c.messages_count > 0)
            .order_by(desc(subquery.c.messages_count))
            .limit(limit)
        )

        result = await session.execute(query)
        rows = result.all()

        # Получаем активные подписки для этих пользователей
        user_ids = [row[0].id for row in rows]
        subscriptions_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id.in_(user_ids))
            .where(Subscription.is_active == True)
            .where(Subscription.expires_at > datetime.now())
        )
        active_subs = {sub.user_id: sub for sub in subscriptions_result.scalars().all()}

        # Получаем последние настроения пользователей
        from database.models import MoodEntry
        moods_result = await session.execute(
            select(MoodEntry)
            .where(MoodEntry.user_id.in_(user_ids))
            .order_by(MoodEntry.created_at.desc())
        )

        # Группируем по user_id, берём последнее
        last_moods = {}
        for mood in moods_result.scalars().all():
            if mood.user_id not in last_moods:
                last_moods[mood.user_id] = mood

        # Маппинг эмоций на эмоджи
        emotion_emoji_map = {
            "happy": "😊",
            "sad": "😢",
            "anxious": "😰",
            "angry": "😠",
            "neutral": "😐",
            "excited": "🤗",
            "tired": "😴",
            "frustrated": "😤",
            "grateful": "🙏",
            "hopeful": "✨",
        }

        top_users = []
        for user, messages_count in rows:
            sub = active_subs.get(user.id)
            is_premium = sub is not None and sub.plan == "premium"

            # Получаем настроение
            mood = last_moods.get(user.id)
            mood_emoji = None
            primary_emotion = None
            if mood:
                primary_emotion = mood.primary_emotion
                mood_emoji = emotion_emoji_map.get(primary_emotion, "😐")

            top_users.append({
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "is_premium": is_premium,
                "messages_this_week": messages_count or 0,
                "mood_emoji": mood_emoji,
                "primary_emotion": primary_emotion,
            })

        return top_users


@router.get("/users/{telegram_id}/export/history")
async def export_user_history_admin(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """Экспортировать историю пользователя (для админа)."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить все сообщения
    messages, _ = await conv_repo.get_paginated(user.id, page=1, per_page=10000)

    # Создать CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата", "Роль", "Сообщение", "Тип", "Теги"])

    for msg in reversed(messages):
        writer.writerow([
            msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "User" if msg.role == "user" else "Mira",
            msg.content,
            msg.message_type or "text",
            ", ".join(msg.tags) if msg.tags else ""
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=admin_export_{telegram_id}_history.csv"
        }
    )


class MessageItem(BaseModel):
    """Сообщение из переписки."""
    id: int
    role: str
    content: str
    created_at: datetime
    message_type: Optional[str]
    tags: List[str]
    file_url: Optional[str] = None  # URL файла (фото/голосовое)


@router.get("/users/{telegram_id}/messages", response_model=List[MessageItem])
async def get_user_messages(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
    limit: int = Query(default=200, le=1000),
):
    """Получить сообщения пользователя для просмотра."""
    from database.repositories.user_file import UserFileRepository
    from services.storage.gcs_client import gcs_client

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить последние сообщения
    messages, _ = await conv_repo.get_paginated(user.id, page=1, per_page=limit)

    # Получить файлы пользователя для сопоставления
    file_repo = UserFileRepository()
    user_files = await file_repo.get_user_files(user.id)

    # Создать словарь файлов по времени создания (округлённому до минуты)
    files_by_time = {}
    for f in user_files:
        if not f.is_deleted and f.gcs_path:
            # Округляем время до минуты для сопоставления
            time_key = f.created_at.replace(second=0, microsecond=0)
            files_by_time[time_key] = f

    # Вернуть в обратном порядке (от старых к новым)
    result = []
    for msg in reversed(messages):
        file_url = None

        # Если сообщение с тегами photo или voice - ищем файл
        tags = msg.tags or []
        if "photo" in tags or msg.message_type == "voice":
            msg_time = msg.created_at.replace(second=0, microsecond=0)
            # Ищем файл в пределах ±1 минуты
            for offset in [0, -1, 1]:
                from datetime import timedelta
                check_time = msg_time + timedelta(minutes=offset)
                if check_time in files_by_time:
                    f = files_by_time[check_time]
                    # Проверяем тип файла
                    if ("photo" in tags and f.file_type == "photo") or \
                       (msg.message_type == "voice" and f.file_type == "voice"):
                        # Генерируем signed URL
                        signed_url = await gcs_client.get_signed_url(f.gcs_path, expiration_minutes=60)
                        if signed_url:
                            file_url = signed_url
                        elif gcs_client.is_available:
                            # Fallback: публичный URL
                            file_url = gcs_client.get_public_url(f.gcs_path)
                        break

        result.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at,
            "message_type": msg.message_type,
            "tags": tags,
            "file_url": file_url
        })

    return result


class UserFileItem(BaseModel):
    """Файл пользователя."""
    id: int
    file_type: str
    gcs_path: str
    gcs_url: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    created_at: datetime
    expires_at: datetime


@router.get("/users/{telegram_id}/files", response_model=List[UserFileItem])
async def get_user_files(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
    limit: int = Query(default=100, le=500),
):
    """Получить файлы пользователя из GCS."""
    from database.repositories.user_file import UserFileRepository
    from services.storage.gcs_client import gcs_client

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    file_repo = UserFileRepository()
    files = await file_repo.get_user_files(user.id, include_deleted=False)

    result = []
    for f in files[:limit]:
        # Генерируем signed URL для просмотра
        file_url = None
        if f.gcs_path:
            if gcs_client.is_available:
                signed_url = await gcs_client.get_signed_url(f.gcs_path, expiration_minutes=60)
                if signed_url:
                    file_url = signed_url
                else:
                    # Fallback: публичный URL
                    file_url = gcs_client.get_public_url(f.gcs_path)
            else:
                # GCS недоступен - возвращаем None
                file_url = None

        result.append({
            "id": f.id,
            "file_type": f.file_type,
            "gcs_path": f.gcs_path,
            "gcs_url": file_url,
            "file_name": f.file_name,
            "file_size": f.file_size,
            "mime_type": f.mime_type,
            "created_at": f.created_at,
            "expires_at": f.expires_at,
        })

    return result


# ========== Analytics Endpoints ==========


class ActivityDataResponse(BaseModel):
    """Данные графика активности."""
    labels: List[str]
    active_users: List[int]
    messages: List[int]


class SubscriptionsDataResponse(BaseModel):
    """Данные распределения подписок."""
    labels: List[str]
    values: List[int]


@router.get("/analytics/activity", response_model=ActivityDataResponse)
async def get_activity_analytics(
    _admin: dict = Depends(require_admin),
    days: int = Query(default=7, ge=1, le=90),
):
    """Получить данные активности по дням."""
    from database.session import get_session_context
    from database.models import User, Message
    from sqlalchemy import select, func, and_
    from datetime import date

    labels = []
    active_users = []
    messages_counts = []

    async with get_session_context() as session:
        for i in range(days - 1, -1, -1):
            day = date.today() - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())

            # Активные пользователи (last_active_at в этот день)
            active_result = await session.execute(
                select(func.count(User.id.distinct())).where(
                    and_(
                        User.last_active_at >= day_start,
                        User.last_active_at <= day_end
                    )
                )
            )
            active_count = active_result.scalar() or 0

            # Сообщения за день
            messages_result = await session.execute(
                select(func.count(Message.id)).where(
                    and_(
                        Message.created_at >= day_start,
                        Message.created_at <= day_end
                    )
                )
            )
            messages_count = messages_result.scalar() or 0

            # Форматируем дату
            label = day.strftime("%d.%m")
            labels.append(label)
            active_users.append(active_count)
            messages_counts.append(messages_count)

    return {
        "labels": labels,
        "active_users": active_users,
        "messages": messages_counts,
    }


@router.get("/analytics/subscriptions", response_model=SubscriptionsDataResponse)
async def get_subscriptions_analytics(
    _admin: dict = Depends(require_admin),
):
    """Получить распределение подписок."""
    from database.session import get_session_context
    from database.models import Subscription, User
    from sqlalchemy import select, func

    async with get_session_context() as session:
        # Количество активных подписок по типам
        result = await session.execute(
            select(
                Subscription.plan,
                func.count(Subscription.id)
            ).where(
                Subscription.expires_at > datetime.now()
            ).group_by(Subscription.plan)
        )

        plan_counts = dict(result.all())

        # Пользователи без подписок считаются Free
        total_users_result = await session.execute(
            select(func.count()).select_from(User)
        )
        total_users = total_users_result.scalar() or 0

        premium_count = plan_counts.get("premium", 0)
        trial_count = plan_counts.get("trial", 0)
        free_count = total_users - premium_count - trial_count

    return {
        "labels": ["Premium", "Trial", "Free"],
        "values": [premium_count, trial_count, free_count],
    }


class MoodOverTimeResponse(BaseModel):
    """Данные графика настроения по дням."""
    labels: List[str]
    average_mood: List[float]
    entry_counts: List[int]


class EmotionDistributionResponse(BaseModel):
    """Распределение эмоций."""
    labels: List[str]
    values: List[int]


class TopTagsResponse(BaseModel):
    """Топ-5 тегов сообщений."""
    labels: List[str]
    values: List[int]


@router.get("/analytics/mood", response_model=MoodOverTimeResponse)
async def get_mood_analytics(
    _admin: dict = Depends(require_admin),
    days: int = Query(default=30, ge=7, le=90),
):
    """Получить данные настроения по дням."""
    from database.session import get_session_context
    from database.models import MoodEntry
    from sqlalchemy import select, func, and_
    from datetime import date

    labels = []
    average_moods = []
    entry_counts = []

    async with get_session_context() as session:
        for i in range(days - 1, -1, -1):
            day = date.today() - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())

            # Средний mood_score за день
            avg_result = await session.execute(
                select(func.avg(MoodEntry.mood_score)).where(
                    and_(
                        MoodEntry.created_at >= day_start,
                        MoodEntry.created_at <= day_end
                    )
                )
            )
            avg_mood = avg_result.scalar()

            # Количество записей за день
            count_result = await session.execute(
                select(func.count(MoodEntry.id)).where(
                    and_(
                        MoodEntry.created_at >= day_start,
                        MoodEntry.created_at <= day_end
                    )
                )
            )
            entry_count = count_result.scalar() or 0

            label = day.strftime("%d.%m")
            labels.append(label)
            average_moods.append(round(avg_mood, 1) if avg_mood else 0)
            entry_counts.append(entry_count)

    return {
        "labels": labels,
        "average_mood": average_moods,
        "entry_counts": entry_counts,
    }


@router.get("/analytics/emotions", response_model=EmotionDistributionResponse)
async def get_emotions_analytics(
    _admin: dict = Depends(require_admin),
    days: int = Query(default=30, ge=7, le=90),
):
    """Получить распределение эмоций."""
    from database.session import get_session_context
    from database.models import MoodEntry
    from sqlalchemy import select, func

    async with get_session_context() as session:
        cutoff = datetime.now() - timedelta(days=days)

        # Подсчитываем количество каждой эмоции
        result = await session.execute(
            select(
                MoodEntry.primary_emotion,
                func.count(MoodEntry.id)
            ).where(
                MoodEntry.created_at >= cutoff
            ).group_by(MoodEntry.primary_emotion)
            .order_by(func.count(MoodEntry.id).desc())
        )

        emotion_counts = dict(result.all())

        # Эмоции на русском для UI
        emotion_labels_ru = {
            "joy": "Радость",
            "sadness": "Грусть",
            "anxiety": "Тревога",
            "anger": "Гнев",
            "fear": "Страх",
            "calm": "Спокойствие",
            "frustration": "Раздражение",
            "hope": "Надежда",
            "loneliness": "Одиночество",
            "overwhelmed": "Перегружена",
            "neutral": "Нейтрально",
        }

        labels = []
        values = []

        for emotion, count in emotion_counts.items():
            label = emotion_labels_ru.get(emotion, emotion.capitalize())
            labels.append(label)
            values.append(count)

    return {
        "labels": labels,
        "values": values,
    }


@router.get("/analytics/tags", response_model=TopTagsResponse)
async def get_top_tags(
    _admin: dict = Depends(require_admin),
    days: int = Query(default=30, ge=7, le=90),
):
    """Получить топ-5 тегов сообщений."""
    from database.session import get_session_context
    from database.models import Message
    from sqlalchemy import select, func, and_

    async with get_session_context() as session:
        cutoff = datetime.now() - timedelta(days=days)

        # Получить все сообщения за период
        result = await session.execute(
            select(Message.tags).where(
                and_(
                    Message.created_at >= cutoff,
                    Message.tags.isnot(None),
                    func.array_length(Message.tags, 1) > 0
                )
            )
        )

        messages = result.scalars().all()

        # Подсчитываем теги
        tag_counts = {}
        for tags_array in messages:
            if tags_array:
                for tag in tags_array:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Сортируем и берём топ-5
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        labels = [tag for tag, _ in top_tags]
        values = [count for _, count in top_tags]

    return {
        "labels": labels,
        "values": values,
    }


class RetentionMetricsResponse(BaseModel):
    """Retention метрики."""
    dau: int  # Daily Active Users
    wau: int  # Weekly Active Users
    mau: int  # Monthly Active Users
    dau_wau_ratio: float  # Stickiness
    wau_mau_ratio: float


class BroadcastRequest(BaseModel):
    """Запрос на массовую рассылку."""
    message: str
    target_group: str  # "all", "premium", "trial", "free", "active_today", "active_week", "inactive"
    delay_seconds: Optional[int] = 1  # Задержка между сообщениями


class BroadcastResponse(BaseModel):
    """Ответ на запрос рассылки."""
    status: str
    task_id: str
    target_users_count: int
    message: str


@router.get("/analytics/retention", response_model=RetentionMetricsResponse)
async def get_retention_metrics(
    _admin: dict = Depends(require_admin),
):
    """Получить retention метрики (DAU/WAU/MAU)."""
    from database.session import get_session_context
    from database.models import User
    from sqlalchemy import select, func

    now = datetime.now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    async with get_session_context() as session:
        # DAU - активные за последние 24 часа
        dau_result = await session.execute(
            select(func.count(User.id.distinct())).where(
                User.last_active_at >= day_ago
            )
        )
        dau = dau_result.scalar() or 0

        # WAU - активные за последние 7 дней
        wau_result = await session.execute(
            select(func.count(User.id.distinct())).where(
                User.last_active_at >= week_ago
            )
        )
        wau = wau_result.scalar() or 0

        # MAU - активные за последние 30 дней
        mau_result = await session.execute(
            select(func.count(User.id.distinct())).where(
                User.last_active_at >= month_ago
            )
        )
        mau = mau_result.scalar() or 0

    # Расчет stickiness (DAU/WAU и WAU/MAU)
    dau_wau_ratio = round((dau / wau * 100) if wau > 0 else 0, 1)
    wau_mau_ratio = round((wau / mau * 100) if mau > 0 else 0, 1)

    return {
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "dau_wau_ratio": dau_wau_ratio,
        "wau_mau_ratio": wau_mau_ratio,
    }


# ========== Broadcast Endpoints ==========


@router.post("/broadcast", response_model=BroadcastResponse)
async def create_broadcast(
    request: BroadcastRequest,
    _admin: dict = Depends(require_admin),
):
    """Создать массовую рассылку."""
    from database.session import get_session_context
    from database.models import User, Subscription
    from sqlalchemy import select, and_, or_
    import uuid

    async with get_session_context() as session:
        # Определить целевую группу пользователей
        query = select(User.telegram_id).where(User.is_blocked == False)

        if request.target_group == "premium":
            # Пользователи с активной Premium подпиской
            premium_user_ids = await session.execute(
                select(Subscription.user_id).where(
                    and_(
                        Subscription.plan == "premium",
                        Subscription.expires_at > datetime.now()
                    )
                )
            )
            premium_user_ids = [uid for (uid,) in premium_user_ids.all()]
            query = query.where(User.id.in_(premium_user_ids))

        elif request.target_group == "trial":
            # Пользователи с активной Trial подпиской
            trial_user_ids = await session.execute(
                select(Subscription.user_id).where(
                    and_(
                        Subscription.plan == "trial",
                        Subscription.expires_at > datetime.now()
                    )
                )
            )
            trial_user_ids = [uid for (uid,) in trial_user_ids.all()]
            query = query.where(User.id.in_(trial_user_ids))

        elif request.target_group == "free":
            # Пользователи без активной подписки
            active_subscription_user_ids = await session.execute(
                select(Subscription.user_id).where(
                    Subscription.expires_at > datetime.now()
                )
            )
            active_subscription_user_ids = [uid for (uid,) in active_subscription_user_ids.all()]
            query = query.where(User.id.notin_(active_subscription_user_ids))

        elif request.target_group == "active_today":
            # Активны сегодня
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.where(User.last_active_at >= today_start)

        elif request.target_group == "active_week":
            # Активны за неделю
            week_ago = datetime.now() - timedelta(days=7)
            query = query.where(User.last_active_at >= week_ago)

        elif request.target_group == "inactive":
            # Неактивны >30 дней
            month_ago = datetime.now() - timedelta(days=30)
            query = query.where(
                or_(
                    User.last_active_at < month_ago,
                    User.last_active_at.is_(None)
                )
            )

        # "all" - не добавляем дополнительных фильтров

        result = await session.execute(query)
        telegram_ids = [tid for (tid,) in result.all()]

    # Генерируем уникальный ID для задачи
    task_id = str(uuid.uuid4())

    # Запускаем рассылку в фоне
    import asyncio
    import httpx

    async def send_broadcast():
        """Фоновая задача для рассылки."""
        logger.info(f"Starting broadcast {task_id} to {len(telegram_ids)} users")

        success_count = 0
        fail_count = 0

        async with httpx.AsyncClient() as client:
            for tid in telegram_ids:
                try:
                    response = await client.post(
                        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": tid,
                            "text": request.message,
                            "parse_mode": "Markdown"
                        },
                        timeout=10.0
                    )
                    result = response.json()
                    if result.get("ok"):
                        success_count += 1
                        logger.debug(f"Broadcast message sent to {tid}")
                    else:
                        fail_count += 1
                        logger.warning(f"Failed to send broadcast to {tid}: {result.get('description')}")
                except Exception as e:
                    fail_count += 1
                    logger.warning(f"Failed to send broadcast to {tid}: {e}")

                # Задержка между сообщениями
                if request.delay_seconds and request.delay_seconds > 0:
                    await asyncio.sleep(request.delay_seconds)

        logger.info(
            f"Broadcast {task_id} completed: {success_count} success, {fail_count} failed"
        )

    # Запускаем в фоне
    asyncio.create_task(send_broadcast())

    return {
        "status": "started",
        "task_id": task_id,
        "target_users_count": len(telegram_ids),
        "message": f"Рассылка запущена для {len(telegram_ids)} пользователей"
    }


# ========== Promo Codes Endpoints ==========


class PromoCodeCreate(BaseModel):
    """Создание промо-кода."""
    code: str
    promo_type: str  # discount_percent, discount_amount, free_days, free_trial
    value: float
    max_uses: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    applicable_plans: Optional[List[str]] = None
    description: Optional[str] = None


class PromoCodeUpdate(BaseModel):
    """Обновление промо-кода."""
    promo_type: Optional[str] = None
    value: Optional[float] = None
    max_uses: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    applicable_plans: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PromoCodeResponse(BaseModel):
    """Ответ с промо-кодом."""
    id: int
    code: str
    promo_type: str
    value: float
    max_uses: Optional[int]
    current_uses: int
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
    applicable_plans: Optional[List[str]]
    is_active: bool
    description: Optional[str]
    created_at: datetime


class PromoCodeUsageResponse(BaseModel):
    """Ответ с историей использования промо-кода."""
    id: int
    code: str
    user_id: int
    telegram_id: int
    username: Optional[str]
    display_name: Optional[str]
    used_at: datetime
    discount_amount: Optional[float]
    free_days_granted: Optional[int]


@router.get("/promo-codes", response_model=List[PromoCodeResponse])
async def list_promo_codes(
    _admin: dict = Depends(require_admin),
    active_only: bool = False,
):
    """Получить список всех промо-кодов."""
    from database.session import get_session_context
    from database.models import PromoCode
    from sqlalchemy import select

    async with get_session_context() as session:
        query = select(PromoCode).order_by(PromoCode.created_at.desc())

        if active_only:
            query = query.where(PromoCode.is_active == True)

        result = await session.execute(query)
        promos = result.scalars().all()

        return [
            {
                "id": p.id,
                "code": p.code,
                "promo_type": p.promo_type,
                "value": p.value,
                "max_uses": p.max_uses,
                "current_uses": p.current_uses,
                "valid_from": p.valid_from,
                "valid_until": p.valid_until,
                "applicable_plans": p.applicable_plans,
                "is_active": p.is_active,
                "description": p.description,
                "created_at": p.created_at,
            }
            for p in promos
        ]


@router.post("/promo-codes", response_model=PromoCodeResponse)
async def create_promo_code(
    promo: PromoCodeCreate,
    _admin: dict = Depends(require_admin),
):
    """Создать новый промо-код."""
    # Проверяем что код уникален
    existing = await promo_repo.get_by_code(promo.code)
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")

    # Создаём промо-код
    new_promo = await promo_repo.create(
        code=promo.code.upper(),
        promo_type=promo.promo_type,
        value=promo.value,
        max_uses=promo.max_uses,
        valid_from=promo.valid_from,
        valid_until=promo.valid_until,
        applicable_plans=promo.applicable_plans,
        description=promo.description,
    )

    return {
        "id": new_promo.id,
        "code": new_promo.code,
        "promo_type": new_promo.promo_type,
        "value": new_promo.value,
        "max_uses": new_promo.max_uses,
        "current_uses": new_promo.current_uses,
        "valid_from": new_promo.valid_from,
        "valid_until": new_promo.valid_until,
        "applicable_plans": new_promo.applicable_plans,
        "is_active": new_promo.is_active,
        "description": new_promo.description,
        "created_at": new_promo.created_at,
    }


@router.get("/promo-codes/{promo_id}", response_model=PromoCodeResponse)
async def get_promo_code(
    promo_id: int,
    _admin: dict = Depends(require_admin),
):
    """Получить промо-код по ID."""
    promo = await promo_repo.get(promo_id)

    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")

    return {
        "id": promo.id,
        "code": promo.code,
        "promo_type": promo.promo_type,
        "value": promo.value,
        "max_uses": promo.max_uses,
        "current_uses": promo.current_uses,
        "valid_from": promo.valid_from,
        "valid_until": promo.valid_until,
        "applicable_plans": promo.applicable_plans,
        "is_active": promo.is_active,
        "description": promo.description,
        "created_at": promo.created_at,
    }


@router.put("/promo-codes/{promo_id}", response_model=PromoCodeResponse)
async def update_promo_code(
    promo_id: int,
    update_data: PromoCodeUpdate,
    _admin: dict = Depends(require_admin),
):
    """Обновить промо-код."""
    promo = await promo_repo.get(promo_id)

    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")

    # Формируем данные для обновления
    update_dict = {}
    if update_data.promo_type is not None:
        update_dict["promo_type"] = update_data.promo_type
    if update_data.value is not None:
        update_dict["value"] = update_data.value
    if update_data.max_uses is not None:
        update_dict["max_uses"] = update_data.max_uses
    if update_data.valid_from is not None:
        update_dict["valid_from"] = update_data.valid_from
    if update_data.valid_until is not None:
        update_dict["valid_until"] = update_data.valid_until
    if update_data.applicable_plans is not None:
        update_dict["applicable_plans"] = update_data.applicable_plans
    if update_data.description is not None:
        update_dict["description"] = update_data.description
    if update_data.is_active is not None:
        update_dict["is_active"] = update_data.is_active

    updated_promo = await promo_repo.update(promo_id, **update_dict)

    return {
        "id": updated_promo.id,
        "code": updated_promo.code,
        "promo_type": updated_promo.promo_type,
        "value": updated_promo.value,
        "max_uses": updated_promo.max_uses,
        "current_uses": updated_promo.current_uses,
        "valid_from": updated_promo.valid_from,
        "valid_until": updated_promo.valid_until,
        "applicable_plans": updated_promo.applicable_plans,
        "is_active": updated_promo.is_active,
        "description": updated_promo.description,
        "created_at": updated_promo.created_at,
    }


@router.delete("/promo-codes/{promo_id}")
async def delete_promo_code(
    promo_id: int,
    _admin: dict = Depends(require_admin),
):
    """Удалить промо-код (деактивировать)."""
    promo = await promo_repo.get(promo_id)

    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")

    await promo_repo.deactivate(promo_id)

    return {"status": "ok", "message": "Promo code deactivated"}


@router.get("/promo-codes/{promo_id}/usage", response_model=List[PromoCodeUsageResponse])
async def get_promo_code_usage(
    promo_id: int,
    _admin: dict = Depends(require_admin),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, le=200),
):
    """Получить историю использования промо-кода."""
    promo = await promo_repo.get(promo_id)

    if not promo:
        raise HTTPException(status_code=404, detail="Promo code not found")

    usage_list, total = await promo_repo.get_usage_history(
        promo_code_id=promo_id,
        page=page,
        per_page=per_page,
    )

    return usage_list


@router.get("/promo-usage", response_model=List[PromoCodeUsageResponse])
async def get_all_promo_usage(
    _admin: dict = Depends(require_admin),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, le=200),
):
    """Получить всю историю использования промо-кодов."""
    usage_list, total = await promo_repo.get_usage_history(
        page=page,
        per_page=per_page,
    )

    return usage_list


# ========== System Settings Endpoints ==========


from database.repositories.settings import settings_repo, promotion_repo as promo_promotion_repo, payment_stats_repo


class SettingItem(BaseModel):
    """Элемент настройки."""
    key: str
    value: Optional[str]
    value_type: str
    description: Optional[str]
    is_secret: bool
    updated_at: Optional[datetime]


class SettingCreate(BaseModel):
    """Создание настройки."""
    key: str
    value: str
    value_type: str = "string"  # string, int, float, bool, json
    description: Optional[str] = None
    is_secret: bool = False


class SettingUpdate(BaseModel):
    """Обновление настройки."""
    value: str
    value_type: Optional[str] = None
    description: Optional[str] = None
    is_secret: Optional[bool] = None


@router.get("/settings")
async def list_settings(
    _admin: dict = Depends(require_admin),
    include_secrets: bool = False,
):
    """Получить все системные настройки."""
    all_settings = await settings_repo.get_all(include_secrets=include_secrets)
    return all_settings


@router.get("/settings/{key}")
async def get_setting(
    key: str,
    _admin: dict = Depends(require_admin),
):
    """Получить значение настройки."""
    value = await settings_repo.get(key)
    setting = await settings_repo.get_raw(key)

    if setting is None:
        raise HTTPException(status_code=404, detail="Setting not found")

    return {
        "key": key,
        "value": "***" if setting.is_secret else value,
        "value_type": setting.value_type,
        "description": setting.description,
        "is_secret": setting.is_secret,
    }


@router.post("/settings")
async def create_setting(
    setting_data: SettingCreate,
    _admin: dict = Depends(require_admin),
):
    """Создать или обновить настройку."""
    setting = await settings_repo.set(
        key=setting_data.key,
        value=setting_data.value,
        value_type=setting_data.value_type,
        description=setting_data.description,
        is_secret=setting_data.is_secret,
    )

    return {
        "status": "ok",
        "key": setting.key,
        "message": f"Setting '{setting.key}' saved",
    }


@router.put("/settings/{key}")
async def update_setting(
    key: str,
    update_data: SettingUpdate,
    _admin: dict = Depends(require_admin),
):
    """Обновить настройку."""
    existing = await settings_repo.get_raw(key)

    if existing is None:
        raise HTTPException(status_code=404, detail="Setting not found")

    setting = await settings_repo.set(
        key=key,
        value=update_data.value,
        value_type=update_data.value_type or existing.value_type,
        description=update_data.description if update_data.description is not None else existing.description,
        is_secret=update_data.is_secret if update_data.is_secret is not None else existing.is_secret,
    )

    return {
        "status": "ok",
        "key": setting.key,
        "message": f"Setting '{setting.key}' updated",
    }


@router.delete("/settings/{key}")
async def delete_setting(
    key: str,
    _admin: dict = Depends(require_admin),
):
    """Удалить настройку."""
    deleted = await settings_repo.delete(key)

    if not deleted:
        raise HTTPException(status_code=404, detail="Setting not found")

    return {"status": "ok", "message": f"Setting '{key}' deleted"}


# ========== Promotions (Sales/Discounts) Endpoints ==========


class PromotionCreate(BaseModel):
    """Создание акции."""
    name: str
    promo_type: str  # discount_percent, discount_amount, free_days
    value: float
    start_date: datetime
    end_date: datetime
    description: Optional[str] = None
    applicable_plans: Optional[List[str]] = None
    max_uses: Optional[int] = None
    min_purchase_amount: Optional[int] = None
    banner_text: Optional[str] = None
    show_in_subscription: bool = True


class PromotionUpdate(BaseModel):
    """Обновление акции."""
    name: Optional[str] = None
    promo_type: Optional[str] = None
    value: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    applicable_plans: Optional[List[str]] = None
    max_uses: Optional[int] = None
    min_purchase_amount: Optional[int] = None
    banner_text: Optional[str] = None
    show_in_subscription: Optional[bool] = None
    is_active: Optional[bool] = None


class PromotionResponse(BaseModel):
    """Ответ с акцией."""
    id: int
    name: str
    description: Optional[str]
    promo_type: str
    value: float
    applicable_plans: List[str]
    start_date: datetime
    end_date: datetime
    is_active: bool
    max_uses: Optional[int]
    current_uses: int
    min_purchase_amount: Optional[int]
    banner_text: Optional[str]
    show_in_subscription: bool
    created_at: datetime


@router.get("/promotions", response_model=List[PromotionResponse])
async def list_promotions(
    _admin: dict = Depends(require_admin),
    active_only: bool = False,
):
    """Получить список всех акций."""
    promotions = await promo_promotion_repo.get_all(active_only=active_only)

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "promo_type": p.promo_type,
            "value": p.value,
            "applicable_plans": p.applicable_plans or [],
            "start_date": p.start_date,
            "end_date": p.end_date,
            "is_active": p.is_active,
            "max_uses": p.max_uses,
            "current_uses": p.current_uses,
            "min_purchase_amount": p.min_purchase_amount,
            "banner_text": p.banner_text,
            "show_in_subscription": p.show_in_subscription,
            "created_at": p.created_at,
        }
        for p in promotions
    ]


@router.post("/promotions", response_model=PromotionResponse)
async def create_promotion(
    promo_data: PromotionCreate,
    _admin: dict = Depends(require_admin),
):
    """Создать новую акцию."""
    promotion = await promo_promotion_repo.create(
        name=promo_data.name,
        promo_type=promo_data.promo_type,
        value=promo_data.value,
        start_date=promo_data.start_date,
        end_date=promo_data.end_date,
        description=promo_data.description,
        applicable_plans=promo_data.applicable_plans,
        max_uses=promo_data.max_uses,
        min_purchase_amount=promo_data.min_purchase_amount,
        banner_text=promo_data.banner_text,
        show_in_subscription=promo_data.show_in_subscription,
    )

    return {
        "id": promotion.id,
        "name": promotion.name,
        "description": promotion.description,
        "promo_type": promotion.promo_type,
        "value": promotion.value,
        "applicable_plans": promotion.applicable_plans or [],
        "start_date": promotion.start_date,
        "end_date": promotion.end_date,
        "is_active": promotion.is_active,
        "max_uses": promotion.max_uses,
        "current_uses": promotion.current_uses,
        "min_purchase_amount": promotion.min_purchase_amount,
        "banner_text": promotion.banner_text,
        "show_in_subscription": promotion.show_in_subscription,
        "created_at": promotion.created_at,
    }


@router.get("/promotions/{promo_id}", response_model=PromotionResponse)
async def get_promotion(
    promo_id: int,
    _admin: dict = Depends(require_admin),
):
    """Получить акцию по ID."""
    promotion = await promo_promotion_repo.get(promo_id)

    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")

    return {
        "id": promotion.id,
        "name": promotion.name,
        "description": promotion.description,
        "promo_type": promotion.promo_type,
        "value": promotion.value,
        "applicable_plans": promotion.applicable_plans or [],
        "start_date": promotion.start_date,
        "end_date": promotion.end_date,
        "is_active": promotion.is_active,
        "max_uses": promotion.max_uses,
        "current_uses": promotion.current_uses,
        "min_purchase_amount": promotion.min_purchase_amount,
        "banner_text": promotion.banner_text,
        "show_in_subscription": promotion.show_in_subscription,
        "created_at": promotion.created_at,
    }


@router.put("/promotions/{promo_id}", response_model=PromotionResponse)
async def update_promotion(
    promo_id: int,
    update_data: PromotionUpdate,
    _admin: dict = Depends(require_admin),
):
    """Обновить акцию."""
    promotion = await promo_promotion_repo.get(promo_id)

    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")

    # Формируем данные для обновления
    update_dict = {}
    for field in ["name", "promo_type", "value", "start_date", "end_date",
                  "description", "applicable_plans", "max_uses",
                  "min_purchase_amount", "banner_text", "show_in_subscription", "is_active"]:
        value = getattr(update_data, field, None)
        if value is not None:
            update_dict[field] = value

    updated_promotion = await promo_promotion_repo.update(promo_id, **update_dict)

    return {
        "id": updated_promotion.id,
        "name": updated_promotion.name,
        "description": updated_promotion.description,
        "promo_type": updated_promotion.promo_type,
        "value": updated_promotion.value,
        "applicable_plans": updated_promotion.applicable_plans or [],
        "start_date": updated_promotion.start_date,
        "end_date": updated_promotion.end_date,
        "is_active": updated_promotion.is_active,
        "max_uses": updated_promotion.max_uses,
        "current_uses": updated_promotion.current_uses,
        "min_purchase_amount": updated_promotion.min_purchase_amount,
        "banner_text": updated_promotion.banner_text,
        "show_in_subscription": updated_promotion.show_in_subscription,
        "created_at": updated_promotion.created_at,
    }


@router.delete("/promotions/{promo_id}")
async def delete_promotion(
    promo_id: int,
    _admin: dict = Depends(require_admin),
):
    """Деактивировать акцию."""
    promotion = await promo_promotion_repo.get(promo_id)

    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")

    await promo_promotion_repo.deactivate(promo_id)

    return {"status": "ok", "message": "Promotion deactivated"}


# ========== Payment Stats Endpoints ==========


class PaymentStatsResponse(BaseModel):
    """Статистика платежей."""
    date: datetime
    yookassa_amount: int
    yookassa_successful: int
    yookassa_failed: int
    crypto_amount: int
    crypto_successful: int
    stars_amount: int
    new_subscriptions: int
    renewals: int
    cancellations: int
    promo_uses: int
    promo_discount_total: int


class PaymentSummaryResponse(BaseModel):
    """Сводка платежей за период."""
    yookassa_total: float
    yookassa_count: int
    crypto_total: float
    crypto_count: int
    stars_total: int
    new_subscriptions: int
    renewals: int
    promo_uses: int
    promo_discount_total: float


@router.get("/payment-stats/summary", response_model=PaymentSummaryResponse)
async def get_payment_summary(
    _admin: dict = Depends(require_admin),
    days: int = Query(default=30, ge=1, le=365),
):
    """Получить сводку платежей за период."""
    summary = await payment_stats_repo.get_summary(days=days)
    return summary


@router.get("/payment-stats/daily")
async def get_daily_payment_stats(
    _admin: dict = Depends(require_admin),
    days: int = Query(default=30, ge=1, le=365),
):
    """Получить статистику платежей по дням."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    stats_list = await payment_stats_repo.get_range(start_date, end_date)

    return [
        {
            "date": s.date.isoformat(),
            "yookassa_amount": s.yookassa_amount / 100,  # В рублях
            "yookassa_successful": s.yookassa_successful,
            "yookassa_failed": s.yookassa_failed,
            "crypto_amount": s.crypto_amount / 100,
            "crypto_successful": s.crypto_successful,
            "stars_amount": s.stars_amount,
            "new_subscriptions": s.new_subscriptions,
            "renewals": s.renewals,
            "cancellations": s.cancellations,
            "promo_uses": s.promo_uses,
            "promo_discount_total": s.promo_discount_total / 100,
        }
        for s in stats_list
    ]


@router.get("/payment-stats/export")
async def export_payment_stats(
    _admin: dict = Depends(require_admin),
    days: int = Query(default=30, ge=1, le=365),
):
    """Экспортировать статистику платежей в CSV."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    stats_list = await payment_stats_repo.get_range(start_date, end_date)

    # Создаём CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Дата",
        "YooKassa (₽)",
        "YooKassa успешных",
        "YooKassa отказов",
        "Crypto (₽)",
        "Crypto успешных",
        "Stars",
        "Новых подписок",
        "Продлений",
        "Отмен",
        "Промо использований",
        "Скидки по промо (₽)",
    ])

    for s in stats_list:
        writer.writerow([
            s.date.strftime("%Y-%m-%d"),
            s.yookassa_amount / 100,
            s.yookassa_successful,
            s.yookassa_failed,
            s.crypto_amount / 100,
            s.crypto_successful,
            s.stars_amount,
            s.new_subscriptions,
            s.renewals,
            s.cancellations,
            s.promo_uses,
            s.promo_discount_total / 100,
        ])

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=payment_stats_{days}_days.csv"
        }
    )


# ========== Tariffs Endpoints ==========


class TariffResponse(BaseModel):
    """Тариф подписки."""
    plan: str
    name: str
    price: int
    original_price: Optional[int]
    duration_days: int
    features: List[str]


@router.get("/tariffs")
async def get_tariffs(
    _admin: dict = Depends(require_admin),
):
    """Получить все тарифы подписки."""
    # Загружаем цены из настроек или используем дефолтные
    monthly_price = await settings_repo.get("price_monthly") or settings.PRICE_MONTHLY
    quarterly_price = await settings_repo.get("price_quarterly") or settings.PRICE_QUARTERLY
    yearly_price = await settings_repo.get("price_yearly") or settings.PRICE_YEARLY

    return [
        {
            "plan": "monthly",
            "name": "1 месяц",
            "price": monthly_price,
            "original_price": None,
            "duration_days": 30,
            "features": ["Безлимитное общение", "Полная память", "Все ритуалы"],
        },
        {
            "plan": "quarterly",
            "name": "3 месяца",
            "price": quarterly_price,
            "original_price": monthly_price * 3,
            "duration_days": 90,
            "features": ["Безлимитное общение", "Полная память", "Все ритуалы", "Экономия 15%"],
        },
        {
            "plan": "yearly",
            "name": "1 год",
            "price": yearly_price,
            "original_price": monthly_price * 12,
            "duration_days": 365,
            "features": ["Безлимитное общение", "Полная память", "Все ритуалы", "Экономия 30%"],
        },
    ]


@router.put("/tariffs/{plan}")
async def update_tariff(
    plan: str,
    price: int,
    _admin: dict = Depends(require_admin),
):
    """Обновить цену тарифа."""
    if plan not in ["monthly", "quarterly", "yearly"]:
        raise HTTPException(status_code=400, detail="Invalid plan. Use: monthly, quarterly, yearly")

    if price < 0:
        raise HTTPException(status_code=400, detail="Price must be positive")

    # Сохраняем в настройки
    await settings_repo.set(
        key=f"price_{plan}",
        value=price,
        value_type="int",
        description=f"Цена тарифа {plan}",
    )

    return {"status": "ok", "plan": plan, "price": price}


# ========== Report Generation Endpoint ==========


class ReportResponse(BaseModel):
    """Ответ с отчётом по переписке."""
    summary: str
    user_name: Optional[str]
    total_messages: int
    first_message_date: Optional[datetime]
    last_message_date: Optional[datetime]
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None


@router.post("/users/{telegram_id}/report", response_model=ReportResponse)
async def generate_user_report(
    telegram_id: int,
    admin_data: dict = Depends(get_current_admin),
):
    """
    Генерирует AI-отчёт по всей переписке с пользователем.

    Анализирует:
    - Основные темы общения
    - Эмоциональное состояние
    - Прогресс и изменения
    - Ключевые события
    """
    import anthropic
    from config.settings import settings

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получаем ВСЕ сообщения пользователя
    messages, total = await conv_repo.get_paginated(user.id, page=1, per_page=5000)

    if not messages:
        raise HTTPException(status_code=400, detail="У пользователя нет сообщений")

    # Формируем текст переписки для анализа
    conversation_text = []
    for msg in reversed(messages):  # От старых к новым
        role = "Пользователь" if msg.role == "user" else "Мира"
        date = msg.created_at.strftime("%d.%m.%Y %H:%M")
        conversation_text.append(f"[{date}] {role}: {msg.content}")

    # Ограничиваем размер текста для API (примерно 100K символов)
    full_text = "\n".join(conversation_text)
    if len(full_text) > 100000:
        # Берём последние 100K символов
        full_text = full_text[-100000:]

    # Имя пользователя
    user_name = user.display_name or user.first_name or f"ID:{telegram_id}"

    # Промпт для генерации отчёта
    analysis_prompt = f"""Проанализируй переписку между пользователем и AI-подругой Мирой.
Пользователь: {user_name}

Составь краткий, но информативный отчёт в формате:

## Общая характеристика
[Кто этот человек, какой у него стиль общения, что важно знать]

## Основные темы
[Какие темы поднимались чаще всего]

## Эмоциональный фон
[Как менялось настроение, какие эмоции преобладали]

## Ключевые события/моменты
[Важные события из жизни, которые упоминались]

## Прогресс и рост
[Есть ли заметный прогресс, изменения в лучшую сторону]

## Точки внимания
[На что стоит обратить внимание, возможные проблемы]

Пиши кратко и по делу. Используй конкретные примеры из переписки где уместно.
Не используй markdown-разметку кроме заголовков ##.

ПЕРЕПИСКА:
{full_text}"""

    try:
        # Создаём клиент Anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Запрос к Claude
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Используем Sonnet для скорости
            max_tokens=2000,
            messages=[
                {"role": "user", "content": analysis_prompt}
            ]
        )

        summary = response.content[0].text

        # Извлекаем информацию о токенах
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        # Рассчитываем стоимость для claude-sonnet-4-20250514
        # Input: $3 per million tokens, Output: $15 per million tokens
        input_cost = (response.usage.input_tokens / 1_000_000) * 3.0
        output_cost = (response.usage.output_tokens / 1_000_000) * 15.0
        cost_usd = round(input_cost + output_cost, 6)

        # Трекаем стоимость API
        from database.repositories.api_cost import ApiCostRepository
        api_cost_repo = ApiCostRepository()
        await api_cost_repo.create(
            user_id=user.id,
            provider='claude',
            operation='generate_report',
            cost_usd=cost_usd,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=tokens_used,
            model="claude-sonnet-4-20250514",
            admin_user_id=admin_data["admin_id"],
        )

        # Сохраняем отчёт в базу данных
        from database.repositories.user_report import UserReportRepository
        report_repo = UserReportRepository()
        await report_repo.create(
            telegram_id=telegram_id,
            content=summary,
            created_by=admin_data["admin_id"],
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации отчёта: {str(e)}"
        )

    # Даты первого и последнего сообщения
    first_msg = messages[-1] if messages else None
    last_msg = messages[0] if messages else None

    return {
        "summary": summary,
        "user_name": user_name,
        "total_messages": total,
        "first_message_date": first_msg.created_at if first_msg else None,
        "last_message_date": last_msg.created_at if last_msg else None,
        "tokens_used": tokens_used,
        "cost_usd": cost_usd,
    }


# ============================================================================
# User Profile (Extended Info)
# ============================================================================


@router.get("/users/{telegram_id}/profile")
async def get_user_profile(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """
    Получить расширенный профиль пользователя (собранный из разговоров).
    """
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return {
            "has_profile": False,
            "user_id": user.id,
            "telegram_id": telegram_id,
            "message": "Профиль ещё не собран",
        }

    # Формируем ответ с собранными данными
    result = {
        "has_profile": True,
        "user_id": user.id,
        "telegram_id": telegram_id,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        # Локация
        "country": profile.country,
        "city": profile.city,
        "location_confidence": profile.confidence_location,
        # Личные данные
        "occupation": profile.occupation,
        "occupation_confidence": profile.confidence_occupation,
        "age": profile.age,
        "birth_year": profile.birth_year,
        "hobbies": profile.hobbies,
        # Партнёр
        "has_partner": profile.has_partner,
        "partner_name": profile.partner_name,
        "partner_age": profile.partner_age,
        "partner_occupation": profile.partner_occupation,
        "partner_hobbies": profile.partner_hobbies,
        "partner_confidence": profile.confidence_partner,
        # Дети
        "has_children": profile.has_children,
        "children_count": profile.children_count,
        "children": profile.children or [],
        "children_confidence": profile.confidence_children,
        # Отношения
        "relationship_start": profile.relationship_start_date.isoformat() if profile.relationship_start_date else None,
        "wedding_date": profile.wedding_date.isoformat() if profile.wedding_date else None,
        "how_met": profile.how_met,
        # Дополнительно
        "pets": profile.pets,
        "living_situation": profile.living_situation,
        "health_notes": profile.health_notes,
        "important_dates": profile.important_dates or [],
    }

    return result


@router.put("/users/{telegram_id}/profile")
async def update_user_profile(
    telegram_id: int,
    data: dict,
    _admin: dict = Depends(require_admin),
):
    """
    Вручную обновить профиль пользователя (для админов).
    """
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Получаем или создаём профиль
    profile = await profile_repo.get_or_create(user.id)

    # Фильтруем только разрешённые поля
    allowed_fields = {
        "country", "city", "occupation", "age", "hobbies",
        "partner_name", "partner_age", "partner_occupation", "partner_hobbies",
        "relationship_start", "wedding_date", "how_met", "notes",
    }

    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    # Обновляем профиль
    updated_profile = await profile_repo.update_profile(user.id, **update_data)

    logger.info(f"Admin updated profile for user {telegram_id}: {list(update_data.keys())}")

    return {
        "success": True,
        "updated_fields": list(update_data.keys()),
        "profile_id": updated_profile.id,
    }


@router.post("/users/{telegram_id}/profile/child")
async def add_child_to_profile(
    telegram_id: int,
    child_data: dict,
    _admin: dict = Depends(require_admin),
):
    """
    Добавить информацию о ребёнке в профиль.
    """
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    name = child_data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Имя ребёнка обязательно")

    profile = await profile_repo.add_child(
        user_id=user.id,
        name=name,
        gender=child_data.get("gender"),
        age=child_data.get("age"),
        hobbies=child_data.get("hobbies"),
    )

    logger.info(f"Admin added child '{name}' to profile for user {telegram_id}")

    return {
        "success": True,
        "children": profile.children,
    }


@router.delete("/users/{telegram_id}/profile")
async def delete_user_profile(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """
    Удалить профиль пользователя (сбросить собранную информацию).
    """
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    profile = await profile_repo.get_by_user_id(user.id)
    if not profile:
        return {"success": True, "message": "Профиль не существует"}

    # Сбрасываем все данные профиля
    await profile_repo.update_profile(
        user_id=user.id,
        country=None,
        city=None,
        occupation=None,
        age=None,
        hobbies=None,
        partner_name=None,
        partner_age=None,
        partner_occupation=None,
        partner_hobbies=None,
        relationship_start=None,
        wedding_date=None,
        how_met=None,
        notes=None,
    )

    # Сбрасываем детей и даты через прямой update
    from sqlalchemy import update
    from database.models import UserProfile
    from database.session import async_session

    async with async_session() as session:
        stmt = update(UserProfile).where(
            UserProfile.user_id == user.id
        ).values(
            children=[],
            important_dates=[],
            location_confidence=None,
            occupation_confidence=None,
            age_confidence=None,
            partner_confidence=None,
            children_confidence=None,
        )
        await session.execute(stmt)
        await session.commit()

    logger.info(f"Admin deleted profile for user {telegram_id}")

    return {"success": True, "message": "Профиль очищен"}


# ============================================================================
# User Topics (Memory Entries)
# ============================================================================


@router.get("/users/{telegram_id}/topics")
async def get_user_topics(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """
    Получить темы разговоров пользователя (из memory_entries).
    """
    from database.models import MemoryEntry
    from database.session import async_session

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    async with async_session() as session:
        result = await session.execute(
            select(
                MemoryEntry.category,
                func.count(MemoryEntry.id).label('count'),
                func.max(MemoryEntry.created_at).label('last_mentioned')
            )
            .where(MemoryEntry.user_id == user.id)
            .group_by(MemoryEntry.category)
            .order_by(desc('count'))
            .limit(20)
        )
        topics = result.fetchall()

    return {
        "topics": [
            {
                "category": t.category,
                "count": t.count,
                "last_mentioned": t.last_mentioned.isoformat() if t.last_mentioned else None
            }
            for t in topics
        ]
    }


# ============================================================================
# User Emotions (Mood Entries)
# ============================================================================


@router.get("/users/{telegram_id}/emotions")
async def get_user_emotions(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
    days: int = Query(default=7, ge=1, le=365),
):
    """
    Получить эмоции пользователя (из mood_entries).
    Параметр days - количество дней для фильтрации (7, 30, 90, 365).
    """
    from database.models import MoodEntry
    from database.session import async_session

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Вычисляем дату начала периода
    cutoff_date = datetime.now() - timedelta(days=days)

    async with async_session() as session:
        avg_result = await session.execute(
            select(func.avg(MoodEntry.mood_score))
            .where(MoodEntry.user_id == user.id)
            .where(MoodEntry.created_at >= cutoff_date)
        )
        average_mood = avg_result.scalar()

        emotions_result = await session.execute(
            select(
                MoodEntry.primary_emotion,
                func.count(MoodEntry.id).label('count')
            )
            .where(MoodEntry.user_id == user.id)
            .where(MoodEntry.created_at >= cutoff_date)
            .group_by(MoodEntry.primary_emotion)
            .order_by(desc('count'))
        )
        emotions = emotions_result.fetchall()

    return {
        "average_mood": float(average_mood) if average_mood else None,
        "emotions": [
            {"emotion": e.primary_emotion, "count": e.count}
            for e in emotions
        ],
        "period_days": days
    }


# ============================================================================
# User Referrals
# ============================================================================


@router.get("/users/{telegram_id}/referrals")
async def get_user_referrals(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """
    Получить рефералов пользователя.
    """
    from database.models import Referral, User
    from database.session import async_session

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    async with async_session() as session:
        ref_code_result = await session.execute(
            select(Referral.code)
            .where(Referral.referrer_id == user.id)
            .limit(1)
        )
        referral_code = ref_code_result.scalar()

        referrals_result = await session.execute(
            select(Referral, User)
            .join(User, User.id == Referral.referred_id, isouter=True)
            .where(Referral.referrer_id == user.id)
            .where(Referral.referred_id.isnot(None))
        )
        referrals_data = referrals_result.fetchall()

        active_count = 0
        referrals_list = []
        for ref, referred_user in referrals_data:
            if referred_user:
                # Получаем статистику сообщений для проверки активности
                from database.repositories.conversation import ConversationRepository
                conv_repo = ConversationRepository()
                stats = await conv_repo.get_user_message_stats(referred_user.id)
                total_messages = stats.get("total", 0)

                referrals_list.append({
                    "name": referred_user.first_name or referred_user.username or "Пользователь",
                    "joined_at": referred_user.created_at.isoformat() if referred_user.created_at else None,
                    "is_active": total_messages > 0
                })
                if total_messages > 0:
                    active_count += 1

    return {
        "referral_code": referral_code,
        "total_invited": len(referrals_list),
        "active_referrals": active_count,
        "referrals": referrals_list
    }


# ============================================================================
# User Payments
# ============================================================================


@router.get("/users/{telegram_id}/payments")
async def get_user_payments(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """
    Получить платежи пользователя.
    """
    from database.models import Payment
    from database.session import async_session

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    async with async_session() as session:
        result = await session.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(50)
        )
        payments = result.scalars().all()

    return {
        "payments": [
            {
                "id": p.id,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.yookassa_status or "unknown",
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "plan": p.subscription_id
            }
            for p in payments
        ]
    }


# ============================================================================
# User Goals
# ============================================================================


@router.get("/users/{telegram_id}/goals")
async def get_user_goals(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
):
    """
    Получить цели пользователя.
    """
    from database.models import UserGoal
    from database.session import async_session

    user = await user_repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    async with async_session() as session:
        result = await session.execute(
            select(UserGoal)
            .where(UserGoal.user_id == user.id)
            .order_by(UserGoal.created_at.desc())
            .limit(20)
        )
        goals = result.scalars().all()

    return {
        "goals": [
            {
                "id": g.id,
                "original_goal": g.original_goal,
                "smart_goal": g.smart_goal,
                "status": g.status,
                "progress": g.progress,
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "created_at": g.created_at.isoformat() if g.created_at else None,
                "next_check_in": g.next_check_in.isoformat() if g.next_check_in else None
            }
            for g in goals
        ]
    }


# ============================================================================
# Legend (Mira Character) Endpoints
# ============================================================================


class PhotoDescriptionUpdate(BaseModel):
    """Обновление описания фотографии."""
    title: Optional[str] = None
    story: Optional[str] = None
    mood: Optional[str] = None
    context: Optional[str] = None
    people: Optional[str] = None
    tags: Optional[List[str]] = None


class PhotoDescriptionCreate(BaseModel):
    """Создание нового описания фотографии."""
    file: str
    title: str
    story: str
    mood: str
    context: str
    people: str
    tags: List[str]


@router.get("/legend")
async def get_legend(
    _admin: dict = Depends(require_admin),
):
    """Получить всю легенду Миры."""
    from ai.prompts.mira_legend import MIRA_LEGEND_DATA, PHOTO_DESCRIPTIONS

    return {
        "legend": MIRA_LEGEND_DATA,
        "photos_count": len(PHOTO_DESCRIPTIONS),
    }


@router.get("/legend/photos")
async def get_legend_photos(
    _admin: dict = Depends(require_admin),
    search: Optional[str] = None,
    person: Optional[str] = None,
):
    """Получить все фотографии с историями."""
    from ai.prompts.mira_legend import PHOTO_DESCRIPTIONS, get_photos_by_tag, get_photos_by_person
    from services.storage import gcs_client

    if search:
        photos = get_photos_by_tag(search)
    elif person:
        photos = get_photos_by_person(person)
    else:
        photos = list(PHOTO_DESCRIPTIONS.values())

    # Добавляем signed URL для каждого фото
    photos_with_urls = []
    for photo in photos:
        photo_copy = dict(photo)
        gcs_path = f"mira/{photo['file']}"

        # Пытаемся получить signed URL
        signed_url = await gcs_client.get_signed_url(gcs_path, expiration_minutes=1440)  # 24 часа

        if signed_url:
            photo_copy["image_url"] = signed_url
        elif gcs_client.is_available:
            # Если GCS доступен, но signed URL не получился - используем публичный URL
            photo_copy["image_url"] = gcs_client.get_public_url(gcs_path)
        else:
            # Fallback: локальный путь (если файлы есть на сервере)
            photo_copy["image_url"] = None

        photos_with_urls.append(photo_copy)

    return {
        "photos": photos_with_urls,
        "total": len(photos_with_urls),
    }


@router.get("/legend/photos/{photo_id}")
async def get_legend_photo(
    photo_id: str,
    _admin: dict = Depends(require_admin),
):
    """Получить конкретную фотографию."""
    from ai.prompts.mira_legend import get_photo_story

    photo = get_photo_story(photo_id)

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    return photo


@router.put("/legend/photos/{photo_id}")
async def update_legend_photo(
    photo_id: str,
    update_data: PhotoDescriptionUpdate,
    _admin: dict = Depends(require_admin),
):
    """Обновить описание фотографии."""
    import importlib
    from pathlib import Path

    # Импортируем текущие данные
    from ai.prompts import mira_legend
    importlib.reload(mira_legend)

    if photo_id not in mira_legend.PHOTO_DESCRIPTIONS:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Обновляем данные
    current = mira_legend.PHOTO_DESCRIPTIONS[photo_id]

    if update_data.title is not None:
        current["title"] = update_data.title
    if update_data.story is not None:
        current["story"] = update_data.story
    if update_data.mood is not None:
        current["mood"] = update_data.mood
    if update_data.context is not None:
        current["context"] = update_data.context
    if update_data.people is not None:
        current["people"] = update_data.people
    if update_data.tags is not None:
        current["tags"] = update_data.tags

    # Сохраняем в файл (перезаписываем PHOTO_DESCRIPTIONS)
    try:
        await _save_photo_descriptions(mira_legend.PHOTO_DESCRIPTIONS)
    except Exception as e:
        logger.error(f"Failed to save photo descriptions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")

    return {"status": "ok", "photo_id": photo_id, "updated": current}


@router.post("/legend/photos")
async def create_legend_photo(
    photo_data: PhotoDescriptionCreate,
    _admin: dict = Depends(require_admin),
):
    """Добавить новую фотографию."""
    import importlib
    from ai.prompts import mira_legend
    importlib.reload(mira_legend)

    # Проверяем что ID уникален
    if photo_data.file in mira_legend.PHOTO_DESCRIPTIONS:
        raise HTTPException(status_code=400, detail="Photo with this ID already exists")

    # Добавляем новое фото
    new_photo = {
        "file": photo_data.file,
        "title": photo_data.title,
        "story": photo_data.story,
        "mood": photo_data.mood,
        "context": photo_data.context,
        "people": photo_data.people,
        "tags": photo_data.tags,
    }

    mira_legend.PHOTO_DESCRIPTIONS[photo_data.file] = new_photo

    # Сохраняем
    try:
        await _save_photo_descriptions(mira_legend.PHOTO_DESCRIPTIONS)
    except Exception as e:
        logger.error(f"Failed to save photo descriptions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")

    return {"status": "ok", "photo_id": photo_data.file, "photo": new_photo}


@router.delete("/legend/photos/{photo_id}")
async def delete_legend_photo(
    photo_id: str,
    _admin: dict = Depends(require_admin),
):
    """Удалить фотографию."""
    import importlib
    from ai.prompts import mira_legend
    importlib.reload(mira_legend)

    if photo_id not in mira_legend.PHOTO_DESCRIPTIONS:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Удаляем
    del mira_legend.PHOTO_DESCRIPTIONS[photo_id]

    # Сохраняем
    try:
        await _save_photo_descriptions(mira_legend.PHOTO_DESCRIPTIONS)
    except Exception as e:
        logger.error(f"Failed to save photo descriptions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")

    return {"status": "ok", "message": f"Photo {photo_id} deleted"}


@router.get("/legend/tags")
async def get_all_tags(
    _admin: dict = Depends(require_admin),
):
    """Получить все уникальные теги фотографий."""
    from ai.prompts.mira_legend import get_all_tags

    tags = get_all_tags()

    return {"tags": tags, "total": len(tags)}


async def _save_photo_descriptions(photo_descriptions: dict):
    """Сохранить описания фотографий в файл mira_legend.py."""
    import aiofiles
    from pathlib import Path

    # Путь к файлу
    file_path = Path(__file__).parent.parent.parent.parent / "ai" / "prompts" / "mira_legend.py"

    # Читаем текущий файл
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()

    # Находим секцию PHOTO_DESCRIPTIONS и заменяем её
    import re

    # Генерируем новый код для PHOTO_DESCRIPTIONS
    new_photos_code = "PHOTO_DESCRIPTIONS = {\n"

    for photo_id, photo_data in photo_descriptions.items():
        story = photo_data.get('story', '').replace('"""', '\\"\\"\\"')
        new_photos_code += f'    "{photo_id}": {{\n'
        new_photos_code += f'        "file": "{photo_data.get("file", photo_id)}",\n'
        new_photos_code += f'        "title": "{photo_data.get("title", "")}",\n'
        new_photos_code += f'        "story": """{story}""",\n'
        new_photos_code += f'        "mood": "{photo_data.get("mood", "")}",\n'
        new_photos_code += f'        "context": "{photo_data.get("context", "")}",\n'
        new_photos_code += f'        "people": "{photo_data.get("people", "")}",\n'

        tags = photo_data.get("tags", [])
        tags_str = ", ".join([f'"{t}"' for t in tags])
        new_photos_code += f'        "tags": [{tags_str}]\n'
        new_photos_code += '    },\n\n'

    new_photos_code += "}\n"

    # Заменяем секцию PHOTO_DESCRIPTIONS
    pattern = r'PHOTO_DESCRIPTIONS = \{.*?\n\}\n'
    new_content = re.sub(pattern, new_photos_code, content, flags=re.DOTALL)

    # Сохраняем
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(new_content)

    logger.info(f"Saved {len(photo_descriptions)} photo descriptions to {file_path}")
