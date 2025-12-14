"""
Statistics API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository
from database.repositories.mood import MoodRepository
from database.repositories.memory import MemoryRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.subscription import SubscriptionRepository

router = APIRouter()
user_repo = UserRepository()
mood_repo = MoodRepository()
memory_repo = MemoryRepository()
conversation_repo = ConversationRepository()
subscription_repo = SubscriptionRepository()


class MoodPoint(BaseModel):
    """Точка графика настроения."""
    date: str
    score: float
    emotion: str


class TopicCount(BaseModel):
    """Количество обсуждений темы."""
    topic: str
    count: int


class StatsResponse(BaseModel):
    """Статистика пользователя."""
    total_messages: int
    messages_this_week: int
    mood_chart: List[MoodPoint]
    top_topics: List[TopicCount]
    top_emotions: Dict[str, int]
    subscription_plan: str
    subscription_days_left: Optional[int]


@router.get("/", response_model=StatsResponse)
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Получить статистику пользователя."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Общее количество сообщений
    total_messages = await conversation_repo.count_by_user(user.id)

    # Сообщения за неделю
    week_ago = datetime.now() - timedelta(days=7)
    messages_this_week = await conversation_repo.count_by_user_since(user.id, week_ago)

    # График настроения за последние 7 дней
    mood_entries = await mood_repo.get_recent(user.id, days=7)
    mood_chart = []

    # Группируем по дням
    mood_by_day: Dict[str, List] = {}
    for entry in mood_entries:
        day_key = entry.created_at.strftime("%Y-%m-%d")
        if day_key not in mood_by_day:
            mood_by_day[day_key] = []
        mood_by_day[day_key].append(entry)

    # Усредняем по дням
    for day_key in sorted(mood_by_day.keys()):
        entries = mood_by_day[day_key]
        avg_score = sum(e.mood_score for e in entries) / len(entries)
        # Берём наиболее частую эмоцию
        emotions = [e.primary_emotion for e in entries if e.primary_emotion]
        top_emotion = max(set(emotions), key=emotions.count) if emotions else "neutral"

        mood_chart.append(MoodPoint(
            date=day_key,
            score=round(avg_score, 2),
            emotion=top_emotion
        ))

    # Топ темы за последний месяц
    topics = await memory_repo.get_recent_topics(user.id, limit=10)
    topic_counts = {}
    for topic in topics:
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    top_topics = [
        TopicCount(topic=t, count=c)
        for t, c in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Топ эмоции
    all_moods = await mood_repo.get_recent(user.id, days=30)
    emotion_counts: Dict[str, int] = {}
    for mood in all_moods:
        if mood.primary_emotion:
            emotion_counts[mood.primary_emotion] = emotion_counts.get(mood.primary_emotion, 0) + 1

    # Подписка
    subscription = await subscription_repo.get_active(user.id)
    plan = subscription.plan if subscription else "free"
    days_left = None

    if subscription and subscription.expires_at:
        delta = subscription.expires_at - datetime.now()
        days_left = max(0, delta.days)

    return StatsResponse(
        total_messages=total_messages,
        messages_this_week=messages_this_week,
        mood_chart=mood_chart,
        top_topics=top_topics,
        top_emotions=emotion_counts,
        subscription_plan=plan,
        subscription_days_left=days_left,
    )


@router.get("/mood/history")
async def get_mood_history(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """Получить историю настроения за N дней."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    mood_entries = await mood_repo.get_recent(user.id, days=days)

    return {
        "entries": [
            {
                "date": entry.created_at.isoformat(),
                "mood_score": entry.mood_score,
                "primary_emotion": entry.primary_emotion,
                "energy_level": entry.energy_level,
                "anxiety_level": entry.anxiety_level,
            }
            for entry in mood_entries
        ]
    }


@router.get("/topics")
async def get_topics(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Получить список обсуждаемых тем."""
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    topics = await memory_repo.get_recent_topics(user.id, limit=limit)

    return {"topics": topics}
