"""
Admin API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.mood import MoodRepository
from database.repositories.subscription import SubscriptionRepository
from config.settings import settings


router = APIRouter()
user_repo = UserRepository()
conv_repo = ConversationRepository()
mood_repo = MoodRepository()
subscription_repo = SubscriptionRepository()


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


class SystemStatsResponse(BaseModel):
    """Системная статистика."""
    total_users: int
    active_users_today: int
    active_users_week: int
    total_messages: int
    messages_today: int
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
    }


@router.post("/users/{telegram_id}/subscription")
async def update_user_subscription(
    telegram_id: int,
    plan: str,
    days: int,
    _admin: dict = Depends(require_admin),
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
    }


@router.post("/users/{telegram_id}/block")
async def block_user(
    telegram_id: int,
    reason: str,
    _admin: dict = Depends(require_admin),
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

    return {"status": "ok", "user_id": user.id, "blocked": True}


@router.post("/users/{telegram_id}/unblock")
async def unblock_user(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
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

    return {"status": "ok", "user_id": user.id, "blocked": False}


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

    # Подписки (требует подсчета через SubscriptionRepository)
    # Пока заглушки
    premium_users = 0
    trial_users = 0
    free_users = total_users

    return {
        "total_users": total_users,
        "active_users_today": active_today,
        "active_users_week": active_week,
        "total_messages": total_messages,
        "messages_today": messages_today,
        "premium_users": premium_users,
        "trial_users": trial_users,
        "free_users": free_users,
    }


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


@router.get("/users/{telegram_id}/messages", response_model=List[MessageItem])
async def get_user_messages(
    telegram_id: int,
    _admin: dict = Depends(require_admin),
    limit: int = Query(default=200, le=1000),
):
    """Получить сообщения пользователя для просмотра."""
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получить последние сообщения
    messages, _ = await conv_repo.get_paginated(user.id, page=1, per_page=limit)

    # Вернуть в обратном порядке (от старых к новым)
    result = []
    for msg in reversed(messages):
        result.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at,
            "message_type": msg.message_type,
            "tags": msg.tags or []
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
    from database.models import Subscription
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
    from sqlalchemy import select, func

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
    from bot.main import app as bot_app
    import asyncio

    async def send_broadcast():
        """Фоновая задача для рассылки."""
        from loguru import logger

        logger.info(f"Starting broadcast {task_id} to {len(telegram_ids)} users")

        success_count = 0
        fail_count = 0

        for telegram_id in telegram_ids:
            try:
                await bot_app.bot.send_message(
                    chat_id=telegram_id,
                    text=request.message,
                    parse_mode="Markdown"
                )
                success_count += 1
                logger.debug(f"Broadcast message sent to {telegram_id}")
            except Exception as e:
                fail_count += 1
                logger.warning(f"Failed to send broadcast to {telegram_id}: {e}")

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
